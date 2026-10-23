"""Minimal bounded flat Parquet reader for Janus research; supports common numpy primitives, BYTE_ARRAY, dictionary + RLE levels, SNAPPY/ZSTD."""
import ctypes, ctypes.util, io, os, struct, math
from thrift.protocol import TCompactProtocol
from thrift.transport import TTransport
from thrift.Thrift import TType
import numpy as np, pandas as pd

def parse_thrift(blob):
    t=TTransport.TMemoryBuffer(blob); p=TCompactProtocol.TCompactProtocol(t)
    def read(ty):
        if ty == TType.STRUCT:
            p.readStructBegin(); d={}
            while True:
                _,tpe,fid=p.readFieldBegin()
                if tpe==TType.STOP: break
                d[fid]=read(tpe); p.readFieldEnd()
            p.readStructEnd(); return d
        if ty == TType.LIST or ty==TType.SET:
            tp,n=p.readListBegin() if ty==TType.LIST else p.readSetBegin()
            v=[read(tp) for _ in range(n)]
            p.readListEnd() if ty==TType.LIST else p.readSetEnd()
            return v
        if ty==TType.MAP:
            a,b,n=p.readMapBegin();v={read(a):read(b) for _ in range(n)}
            p.readMapEnd();return v
        if ty==TType.STRING: return p.readBinary()
        if ty==TType.I16: return p.readI16()
        if ty==TType.I32: return p.readI32()
        if ty==TType.I64: return p.readI64()
        if ty==TType.DOUBLE: return p.readDouble()
        if ty==TType.BOOL: return p.readBool()
        if ty==TType.BYTE:return p.readByte()
        raise NotImplementedError(('thrift-type',ty))
    return read(TType.STRUCT),t.cstringio_buf.tell()

def get_meta(path):
    with open(path,'rb') as f:
        f.seek(-8,2); b=f.read(8); assert b[4:]==b'PAR1'; size=struct.unpack('<I',b[:4])[0]
        f.seek(-8-size,2);meta,_=parse_thrift(f.read(size))
    return meta

SN=ctypes.CDLL(ctypes.util.find_library('snappy'))
SN.snappy_uncompress.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.POINTER(ctypes.c_size_t)]
SN.snappy_uncompress.restype=ctypes.c_int
SN.snappy_uncompressed_length.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
SN.snappy_uncompressed_length.restype=ctypes.c_int
ZS=ctypes.CDLL(ctypes.util.find_library('zstd'))
ZS.ZSTD_decompress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]
ZS.ZSTD_decompress.restype=ctypes.c_size_t

def decompress(b,codec,n=None):
    if codec==0:return b
    if codec==1:
        m=ctypes.c_size_t(); r=SN.snappy_uncompressed_length(b,len(b),ctypes.byref(m));assert r==0
        out=ctypes.create_string_buffer(m.value);r=SN.snappy_uncompress(b,len(b),out,ctypes.byref(m));assert r==0
        return out.raw[:m.value]
    if codec==6:
        out=ctypes.create_string_buffer(n);l=ZS.ZSTD_decompress(out,n,b,len(b));assert l==n,(l,n)
        return out.raw[:l]
    if codec==2:
        import gzip;return gzip.decompress(b)
    raise NotImplementedError(('codec',codec))

def read_uvar(buf, pos):
    n=0;shift=0
    for _ in range(10):
        v=buf[pos];pos+=1;n|=(v&127)<<shift
        if v<128:return n,pos
        shift+=7
    raise ValueError('uvar')

def hybrid(data,n,bitwidth):
    """Decode RLE/bitpacked hybrid; consumes 4 byte len prefix when present separately."""
    if bitwidth==0:return np.zeros(n,dtype=np.int32)
    out=np.empty(n,dtype=np.int32);i=0;pos=0
    while i<n:
        hd,pos=read_uvar(data,pos)
        if hd&1==0:
            count=hd>>1; bytecount=(bitwidth+7)//8
            val=int.from_bytes(data[pos:pos+bytecount],'little');pos+=bytecount
            take=min(count,n-i);out[i:i+take]=val;i+=take
        else:
            groups=hd>>1;bits_total=groups*8*bitwidth;bytes_total=(bits_total+7)//8
            batch=data[pos:pos+bytes_total];pos+=bytes_total
            raw=int.from_bytes(batch,'little');mask=(1<<bitwidth)-1
            take=min(groups*8,n-i)
            for j in range(take):out[i+j]=(raw>>(j*bitwidth))&mask
            i+=take
    return out

def plain(data,physical,count):
    if physical==0: return np.unpackbits(np.frombuffer(data,dtype=np.uint8),bitorder='little')[:count].astype(bool)
    dtypes={1:'<i4',2:'<i8',3:'<i8',4:'<f4',5:'<f8'}
    if physical in dtypes:return np.frombuffer(data,dtype=dtypes[physical],count=count)
    if physical==6:
        result=[];off=0
        for _ in range(count):
            n=struct.unpack_from('<I',data,off)[0];off+=4
            result.append(data[off:off+n]);off+=n
        return np.array(result,dtype=object)
    raise NotImplementedError(('physical',physical))

def decode_column(path,meta,name):
    schema=meta[2];names=[s[4].decode('utf8') for s in schema];
    assert name in names
    idx=names.index(name)-1
    assert idx>=0
    sch=schema[idx+1];physical=sch[1];rep=sch.get(3,0)
    if rep not in (0,1):raise NotImplementedError(('nested',rep))
    max_def=1 if rep==1 else 0
    arr=[]
    with open(path,'rb') as f:
        for rg in meta[4]:
            ch=rg[1][idx][3]
            codec=ch[4];num=ch[5]
            offset=min(ch.get(9,10**18),ch.get(11,10**18));end=offset+ch[7]
            # column chunk compressed total size includes page headers from dictionary offset
            f.seek(offset);found=0;dictionary=None;pieces=[]
            while found<num:
                prefix=f.read(512)
                h,hsize=parse_thrift(prefix)
                f.seek(f.tell()-(512-hsize))
                sz=h[3];psz=h[2];data=f.read(sz);kind=h[1]
                if kind==2:
                    raw=decompress(data,codec,psz)
                    dheader=h[7];dictionary=plain(raw,physical,dheader[1]);continue
                if kind not in (0,3):raise NotImplementedError(('page type',kind))
                if kind==0:
                    header=h[5];page_n=header[1];enc=header[2];raw=decompress(data,codec,psz)
                    pos=0
                    if max_def:
                        # DataPageV1 levels length prefix, bitwidth 1 for optional field
                        size=struct.unpack_from('<I',raw,pos)[0];pos+=4
                        defs=hybrid(raw[pos:pos+size],page_n,1);pos+=size
                    else:defs=np.ones(page_n,dtype=np.int32)
                    vals=raw[pos:]
                else:
                    header=h[8];page_n=header[1];enc=header[4]
                    rep_len=header.get(5,0);def_len=header.get(6,0)
                    raw=data[:rep_len+def_len]+(decompress(data[rep_len+def_len:],codec,psz-rep_len-def_len) if header.get(7,True) else data[rep_len+def_len:])
                    defs=hybrid(raw[rep_len:rep_len+def_len],page_n,1) if max_def else np.ones(page_n,dtype=np.int32)
                    vals=raw[rep_len+def_len:]
                n_valid=int(np.count_nonzero(defs==max_def))
                if enc in (0,): values=plain(vals,physical,n_valid)
                elif enc in (2,8):
                    width=vals[0];ids=hybrid(vals[1:],n_valid,width);assert dictionary is not None
                    values=dictionary[ids]
                else:raise NotImplementedError(('encoding',enc))
                if max_def:
                    z=np.empty(page_n,dtype=object);z[:]=None;z[defs==max_def]=values
                else:z=values
                pieces.append(z);found+=page_n
            assert found==num,(name,found,num)
            arr.extend(pieces)
    merged=np.concatenate(arr)
    return merged

if __name__=='__main__':
 import sys
 for path in sys.argv[1:]:
  m=get_meta(path)
  print(path,'rows',m[3],'rowgroups',len(m[4]),'schema',[(x[4].decode(),x.get(1),x.get(3),x.get(6)) for x in m[2]])
  for chunk in m[4][0][1]:
   z=chunk[3];print('column',z[3], 'physical',z[1],'codec',z[4],'num',z[5],'compressed',z[7],'page',z.get(9),'dictionary',z.get(11),'encodings',z[2])
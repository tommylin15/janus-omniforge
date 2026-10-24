"""Minimal read-only Parquet reader for this Janus research release's flat ZSTD dictionary pages.
Not a general Parquet implementation: fail closed on unsupported structures/encodings.
"""
from parquet_meta_inspect import decode,readval
from thrift.protocol import TCompactProtocol
from thrift.transport import TTransport
from thrift.Thrift import TType
from pathlib import Path
import struct,ctypes,math
from collections import OrderedDict

_lib=ctypes.CDLL('libzstd.so.1')
_lib.ZSTD_decompress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]
_lib.ZSTD_decompress.restype=ctypes.c_size_t
_lib.ZSTD_isError.argtypes=[ctypes.c_size_t];_lib.ZSTD_isError.restype=ctypes.c_uint

def unzip(data,n,codec):
 if codec==0:return data
 if codec!=6:raise ValueError('UNSUPPORTED_COMPRESSION_CODEC:'+str(codec))
 dst=ctypes.create_string_buffer(n)
 src=ctypes.create_string_buffer(data)
 rc=_lib.ZSTD_decompress(dst,len(dst),src,len(data))
 if _lib.ZSTD_isError(rc):raise ValueError('ZSTD_ERROR')
 if rc!=n:raise ValueError(f'DECOMPRESSED_LENGTH_MISMATCH:{rc}:{n}')
 return dst.raw

def leb(data,offset):
 n=0;shift=0
 while True:
  b=data[offset];offset+=1;n|=(b&0x7f)<<shift
  if not b&0x80:return n,offset
  shift+=7

def hybrid(data,bits,total):
 out=[];i=0;stride=(bits+7)//8
 while len(out)<total:
  v,i=leb(data,i)
  if v&1==0:
   n=v>>1;chunk=data[i:i+stride];i+=stride
   z=int.from_bytes(chunk,'little')
   out.extend([z]*(min(n,total-len(out))))
  else:
   groups=v>>1;n=groups*8;nb=groups*8*bits;payload=data[i:i+(nb+7)//8];i+=(nb+7)//8
   z=int.from_bytes(payload,'little');mask=(1<<bits)-1
   out.extend([(z>>(j*bits))&mask for j in range(min(n,total-len(out)))])
 if len(out)!=total:raise ValueError('DECODE_LENGTH')
 return out

def plain(data,count,t):
 if t==5:
  return list(struct.unpack('<'+('d'*count),data[:8*count]))
 if t==1:
  return list(struct.unpack('<'+('i'*count),data[:4*count]))
 if t==2:
  return list(struct.unpack('<'+('q'*count),data[:8*count]))
 if t==6:
  ans=[];pos=0
  for _ in range(count):
   n=struct.unpack_from('<I',data,pos)[0];pos+=4
   ans.append(data[pos:pos+n].decode('utf-8','replace'));pos+=n
  return ans
 raise ValueError('UNSUPPORTED_TYPE:'+str(t))

def read(path,selected=None):
 path=Path(path)
 with path.open('rb') as fd:
  if fd.read(4)!=b'PAR1':raise ValueError('NOT_PARQUET')
  fd.seek(-8,2);size,magic=struct.unpack('<I4s',fd.read(8))
  if magic!=b'PAR1':raise ValueError('PARQUET_FOOTER')
  fd.seek(-8-size,2);m,_=decode(fd.read(size));schema=m[2]
  if len(m[4])!=1 or any(s.get(3)!=1 for s in schema[1:]):raise ValueError('FLAT_SINGLE_ROWGROUP_ONLY')
  names=[s[4].decode() for s in schema[1:]];mapping={name:c for name,c in zip(names,m[4][0][1])}
  cols=selected if selected is not None else names
  out={}
  for col in cols:
   if col not in mapping:raise ValueError('COLUMN_NOT_FOUND:'+col)
   mm=mapping[col][3];typ=mm[1];codec=mm[4];n_total=mm[5];dictionary=None;values=[]
   fd.seek(mm.get(11) if mm.get(11) is not None else mm[9]);
   while len(values)<n_total:
    p=TCompactProtocol.TCompactProtocol(TTransport.TFileObjectTransport(fd));header=readval(p,TType.STRUCT)
    if header[1] not in (0,2):raise ValueError('UNSUPPORTED_PAGE_TYPE')
    compressed=fd.read(header[3]);data=unzip(compressed,header[2],codec)
    if header[1]==2:
     count=header[7][1]
     dictionary=plain(data,count,typ);continue
    page=header[5];count=page[1];encoding=page[2]
    dlen=struct.unpack_from('<I',data,0)[0];defs=hybrid(data[4:4+dlen],1,count)
    payload=data[4+dlen:];nonempty=sum(defs)
    if encoding==8:
     if dictionary is None:raise ValueError('MISSING_DICTIONARY')
     bit_width=payload[0];ids=hybrid(payload[1:],bit_width,nonempty)
     cell=[dictionary[i] for i in ids]
    elif encoding==0:cell=plain(payload,nonempty,typ)
    else:raise ValueError('UNSUPPORTED_ENCODING:'+str(encoding))
    it=iter(cell);values.extend([next(it) if flag else None for flag in defs])
   if len(values)!=n_total:raise ValueError('ROW_COUNT_MISMATCH')
   out[col]=values
  return out

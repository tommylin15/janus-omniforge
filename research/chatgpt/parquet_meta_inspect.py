from thrift.protocol import TCompactProtocol
from thrift.transport import TTransport
from thrift.Thrift import TType
import struct,sys

def readval(p,t):
 if t==TType.BOOL:return p.readBool()
 if t==TType.BYTE:return p.readByte()
 if t==TType.I16:return p.readI16()
 if t==TType.I32:return p.readI32()
 if t==TType.I64:return p.readI64()
 if t==TType.DOUBLE:return p.readDouble()
 if t==TType.STRING:return p.readBinary()
 if t==TType.STRUCT:
  p.readStructBegin();d={}
  while True:
   _,ft,fid=p.readFieldBegin()
   if ft==TType.STOP:break
   d[fid]=readval(p,ft);p.readFieldEnd()
  p.readStructEnd();return d
 if t==TType.LIST or t==TType.SET:
  elem,n=(p.readListBegin() if t==TType.LIST else p.readSetBegin());xs=[readval(p,elem) for _ in range(n)];(p.readListEnd() if t==TType.LIST else p.readSetEnd());return xs
 if t==TType.MAP:
  a,b,n=p.readMapBegin();m={readval(p,a):readval(p,b) for _ in range(n)};p.readMapEnd();return m
 raise ValueError(t)
def decode(raw):
 buf=TTransport.TMemoryBuffer(raw);p=TCompactProtocol.TCompactProtocol(buf);return readval(p,TType.STRUCT),len(raw)-len(buf.read(100000000))
def main(f):
 with open(f,'rb') as fd:
  fd.seek(-8,2);size,magic=struct.unpack('<I4s',fd.read(8));fd.seek(-8-size,2);m,offset=decode(fd.read(size))
 print('meta bytes',size,'offset',offset,'file version',m.get(1),'num_rows',m.get(3),'schema:')
 for x in m[2]: print({k:(v.decode(errors='replace') if isinstance(v,bytes) else v) for k,v in x.items() if k in (1,2,3,4,5,6)})
 print('groups',len(m[4]));g=m[4][0]; print('first group', {k:v for k,v in g.items() if k!=1});
 for c in g[1]:
  mm=c[3]; print(mm.get(3), 'type',mm.get(1),'codec',mm.get(4),'enc',mm.get(2),'val',mm.get(5),'off',mm.get(9),'dictionary',mm.get(11),'comp size',mm.get(7))
if __name__=='__main__':main(sys.argv[1])

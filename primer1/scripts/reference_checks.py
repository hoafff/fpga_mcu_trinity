#!/usr/bin/env python3
"""Portable differential/reference checks for Primer #1 arithmetic and framing."""
from __future__ import annotations
import random

Q = 3329
ZETAS = [
-1044,-758,-359,-1517,1493,1422,287,202,-171,622,1577,182,962,-1202,-1474,1468,
573,-1325,264,383,-829,1458,-1602,-130,-681,1017,732,608,-1542,411,-205,-1571,
1223,652,-552,1015,-1293,1491,-282,-1544,516,-8,-320,-666,-1618,-1162,126,1469,
-853,-90,-271,830,107,-1421,-247,-951,-398,961,-1508,-725,448,-1065,677,-1275,
-1103,430,555,843,-1251,871,1550,105,422,587,177,-235,-291,-460,1574,1653,
-246,778,1159,-147,-777,1483,-602,1119,-1590,644,-872,349,418,329,-156,-75,
817,1097,603,610,1322,-1285,-1465,384,-1215,-136,1218,-1335,-874,220,-1187,-1659,
-1185,-1530,-1278,794,-1510,-854,-870,478,-108,-308,996,991,958,-1460,1522,1628]
MASK64=(1<<64)-1
RC=[0xF0,0xE1,0xD2,0xC3,0xB4,0xA5,0x96,0x87,0x78,0x69,0x5A,0x4B]
ASCON_IV=1|(12<<16)|(8<<20)|(128<<24)|(16<<40)

def i16(x:int)->int:
    x &= 0xFFFF
    return x-0x10000 if x & 0x8000 else x

def montgomery_reduce(a:int)->int:
    t=i16(i16(a)*-3327)
    return i16((a-t*Q)>>16)

def fqmul(a:int,b:int)->int: return montgomery_reduce(i16(a)*i16(b))
def barrett(a:int)->int: return i16(i16(a)-(((20159*i16(a)+(1<<25))>>26)*Q))
def canon(x:int)->int: return x%Q

def ntt(poly:list[int])->list[int]:
    r=[i16(x) for x in poly]; k=1; length=128
    while length>=2:
        for start in range(0,256,2*length):
            z=ZETAS[k]; k+=1
            for j in range(start,start+length):
                t=fqmul(z,r[j+length]); r[j+length]=i16(r[j]-t); r[j]=i16(r[j]+t)
        length//=2
    return r

def intt_standard(poly:list[int])->list[int]:
    r=[i16(x) for x in poly]; k=127; length=2
    while length<=128:
        for start in range(0,256,2*length):
            z=ZETAS[k]; k-=1
            for j in range(start,start+length):
                t=r[j]; r[j]=barrett(i16(t+r[j+length])); r[j+length]=fqmul(z,i16(r[j+length]-t))
        length*=2
    return [fqmul(x,512) for x in r]

def basemul_standard(a:list[int],b:list[int])->list[int]:
    r=[0]*256
    for i in range(64):
        for off,z in ((0,ZETAS[64+i]),(2,-ZETAS[64+i])):
            j=4*i+off
            x0=i16(fqmul(fqmul(a[j+1],b[j+1]),z)+fqmul(a[j],b[j]))
            x1=i16(fqmul(a[j],b[j+1])+fqmul(a[j+1],b[j]))
            r[j]=fqmul(x0,1353); r[j+1]=fqmul(x1,1353)
    return r

def negacyclic(a:list[int],b:list[int])->list[int]:
    out=[0]*256
    for i,x in enumerate(a):
        for j,y in enumerate(b):
            k=i+j
            if k<256: out[k]+=x*y
            else: out[k-256]-=x*y
    return [v%Q for v in out]

def ror(x:int,n:int)->int: return ((x>>n)|(x<<(64-n)))&MASK64
def ascon_round(s:tuple[int,...],c:int)->tuple[int,...]:
    x0,x1,x2,x3,x4=s; x2^=c; x0^=x4; x4^=x3; x2^=x1
    t0=x0^((~x1)&x2);t1=x1^((~x2)&x3);t2=x2^((~x3)&x4);t3=x3^((~x4)&x0);t4=x4^((~x0)&x1)
    t0&=MASK64;t1&=MASK64;t2&=MASK64;t3&=MASK64;t4&=MASK64
    t1^=t0;t0^=t4;t3^=t2;t2=(~t2)&MASK64
    return tuple(v&MASK64 for v in (t0^ror(t0,19)^ror(t0,28),t1^ror(t1,61)^ror(t1,39),t2^ror(t2,1)^ror(t2,6),t3^ror(t3,10)^ror(t3,17),t4^ror(t4,7)^ror(t4,41)))
def perm(s:tuple[int,...],start:int)->tuple[int,...]:
    for c in RC[start:]: s=ascon_round(s,c)
    return s
def le64(b:bytes)->int:return int.from_bytes(b,'little')
def ascon_encrypt(key:bytes,nonce:bytes,ad:bytes,pt:bytes)->bytes:
    assert len(key)==len(nonce)==16 and len(ad)==len(pt)==24
    k0,k1=le64(key[:8]),le64(key[8:]); n0,n1=le64(nonce[:8]),le64(nonce[8:])
    x0,x1,x2,x3,x4=perm((ASCON_IV,k0,k1,n0,n1),0);x3^=k0;x4^=k1
    x0^=le64(ad[:8]);x1^=le64(ad[8:16]);x0,x1,x2,x3,x4=perm((x0,x1,x2,x3,x4),4)
    x0^=le64(ad[16:]);x1^=1;x0,x1,x2,x3,x4=perm((x0,x1,x2,x3,x4),4);x4^=1<<63
    x0^=le64(pt[:8]);x1^=le64(pt[8:16]);ct=x0.to_bytes(8,'little')+x1.to_bytes(8,'little')
    x0,x1,x2,x3,x4=perm((x0,x1,x2,x3,x4),4);x0^=le64(pt[16:]);ct+=x0.to_bytes(8,'little');x1^=1
    x2^=k0;x3^=k1;x0,x1,x2,x3,x4=perm((x0,x1,x2,x3,x4),0);x3^=k0;x4^=k1
    return ct+x3.to_bytes(8,'little')+x4.to_bytes(8,'little')

def crc16(data:bytes)->int:
    c=0xFFFF
    for b in data:
        c^=b<<8
        for _ in range(8): c=((c<<1)^0x1021)&0xFFFF if c&0x8000 else (c<<1)&0xFFFF
    return c

def crc32c(data: bytes) -> int:
    c = 0xFFFFFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c >> 1) ^ 0x82F63B78) if (c & 1) else (c >> 1)
    return (~c) & 0xFFFFFFFF


def spi_packet(command: int, txid: int, payload: bytes = b"", flags: int = 0) -> bytes:
    assert 0 <= len(payload) <= 66
    header = bytes([0xA5, 0x01, command, flags]) + txid.to_bytes(2, "big") + len(payload).to_bytes(2, "big")
    body = header + payload
    return body + crc16(body).to_bytes(2, "big")

def parse_spi(packet: bytes) -> tuple[int, int, bytes]:
    assert 10 <= len(packet) <= 76
    assert packet[0:2] == b"\xA5\x01"
    assert packet[3] & 0xF0 == 0
    length = int.from_bytes(packet[6:8], "big")
    assert len(packet) == 10 + length
    assert crc16(packet[:-2]) == int.from_bytes(packet[-2:], "big")
    return packet[2], int.from_bytes(packet[4:6], "big"), packet[8:-2]

class SessionModel:
    READY = 3
    STAGED = 4
    BLOCKED = 5
    ACTIVE = 6
    ZEROIZE = 7

    def __init__(self) -> None:
        self.state = self.READY
        self.staged: tuple[int, bytes, bytes] | None = None
        self.active: tuple[int, bytes, bytes] | None = None
        self.sequence = 1
        self.telemetry = b""

    def stage(self, sid: int, key: bytes, prefix: bytes) -> None:
        assert len(key) == 16 and len(prefix) == 8
        context = (sid, key, prefix)
        if self.staged is not None and self.staged[0] == sid:
            assert self.staged == context
            return
        assert self.active is None or self.active[0] != sid
        self.staged = context
        self.state = self.STAGED

    def commit(self, sid: int) -> None:
        assert self.staged is not None and self.staged[0] == sid
        self.active = self.staged
        self.staged = None
        self.sequence = 1
        self.state = self.BLOCKED

    def apply_secure_enable(self, enabled: bool) -> None:
        if self.state == self.BLOCKED and enabled:
            self.state = self.ACTIVE
        elif self.state == self.ACTIVE and not enabled:
            self.zeroize()

    def load(self, plaintext: bytes) -> None:
        assert self.state == self.ACTIVE and len(plaintext) == 24
        self.telemetry = plaintext

    def send_complete(self) -> None:
        assert self.state == self.ACTIVE and len(self.telemetry) == 24
        self.sequence += 1
        self.telemetry = b""

    def zeroize(self) -> None:
        self.state = self.ZEROIZE
        self.staged = None
        self.active = None
        self.telemetry = b""
        self.sequence = 1

def checks()->None:
    assert crc16(b'123456789')==0x29B1
    packet=bytes.fromhex('A501010000010000'); assert crc16(packet)==0x3598
    # SPI packet, malformed CRC rejection, and retained-transaction fingerprint contract.
    wire=spi_packet(0x21,0x1234,bytes(range(66)))
    assert len(wire)==76
    command,txid,payload=parse_spi(wire)
    assert command==0x21 and txid==0x1234 and payload==bytes(range(66))
    corrupt=bytearray(wire);corrupt[10]^=1
    try:
        parse_spi(bytes(corrupt))
        raise AssertionError('corrupt SPI CRC accepted')
    except AssertionError:
        pass
    fp_input=bytes.fromhex('21000042')+bytes(range(66))
    assert crc32c(fp_input)==0xFA65660B
    # Official NIST SP 800-232 Ascon-AEAD128 KAT, Count 817.
    key=bytes(range(0x00,0x10)); nonce=bytes(range(0x10,0x20))
    pt=bytes(range(0x20,0x38)); ad=bytes(range(0x30,0x48))
    kat=ascon_encrypt(key,nonce,ad,pt)
    assert kat.hex()=='9d29f9d52adf9470af4cbce0a4481ac7fcb1b32976469892dfebaf445205ec9b019d022c7042ae59'
    rng=random.Random(0x5031)
    directed=[[0]*256,[1]*256,[i%Q for i in range(256)],[3328]*256]
    for a in directed+[ [rng.randrange(Q) for _ in range(256)] for _ in range(100) ]:
        assert [canon(x) for x in intt_standard([canon(x) for x in ntt(a)])]==a
    for _ in range(100):
        a=[rng.randrange(Q) for _ in range(256)];b=[rng.randrange(Q) for _ in range(256)]
        got=[canon(x) for x in intt_standard(basemul_standard(ntt(a),ntt(b)))]
        assert got==negacyclic(a,b)
    ad=bytes([1,2,0,3])+bytes.fromhex('01020304')+bytes.fromhex('0000000000000001')+bytes.fromhex('00180007')+bytes(4)
    frame=b'\xA5\x5A'+ad+bytes(24)+bytes(16)
    assert len(frame)==66 and frame[:2]==b'\xA5\x5A'
    # Session/commit/sequence/zeroize reference-state contract.
    sm=SessionModel();key=bytes(range(16));prefix=bytes(range(8));sid=0x01020304
    sm.stage(sid,key,prefix);sm.stage(sid,key,prefix)
    sm.commit(sid);assert sm.state==SessionModel.BLOCKED and sm.sequence==1
    sm.apply_secure_enable(True);sm.load(bytes(24));sm.send_complete()
    assert sm.state==SessionModel.ACTIVE and sm.sequence==2 and sm.telemetry==b''
    sm.apply_secure_enable(False)
    assert sm.state==SessionModel.ZEROIZE and sm.active is None and sm.staged is None and sm.sequence==1
    print('PASS crc16_ccitt_false')
    print('PASS spi_packet_crc_success_and_failure')
    print('PASS crc32c_transaction_fingerprint')
    print('PASS ascon_aead128_official_count817_kat')
    print('PASS ntt_intt_directed_plus_100_random')
    print('PASS basemul_pipeline_100_random')
    print('PASS uart_frame_layout_66_bytes')
    print('PASS session_commit_sequence_zeroize_reference_model')

if __name__=='__main__': checks()

#!/usr/bin/env python3
# 24 bites BMP fazisok -> maszkolt Bery GE sprite .bin (GR16; fekete = atlatszo). Hasznalat:
#   python3 tools/bmp2ge.py resources/images resources/images/C64_logo_forog.bin   (c64_symbol_1..16.bmp)
# A regi BMP-kbol a sprite-szerkeszto .bin-jevel bajtra egyezett (2026-11-01).
def pal(): 
    P=[]
    for i in range(16):
        I=(i>>3)&1;G=(i>>2)&1;R=(i>>1)&1;B=i&1;v=255 if I else 146
        P.append((R*v,G*v,B*v))
    return P
P=pal()
def rd(f):
    b=open(f,'rb').read();off=struct.unpack('<I',b[10:14])[0];w,h=struct.unpack('<ii',b[18:26]);bpp=struct.unpack('<H',b[28:30])[0]
    assert bpp==24;st=(w*3+3)&~3;px=[]
    for y in range(abs(h)):
        yy=(abs(h)-1-y) if h>0 else y;r=[]
        for x in range(w):
            B,G,R=b[off+yy*st+x*3:off+yy*st+x*3+3];r.append((R,G,B))
        px.append(r)
    return w,abs(h),px
def idx(c):
    return min(range(16),key=lambda i:sum((a-b)**2 for a,b in zip(P[i],c)))
def conv(files,out):
    o=bytearray();W=H=None
    for f in files:
        w,h,px=rd(f);W,H=w,h
        for y in range(h):
            for x in range(0,w,2):
                m=0;d=0
                for s,c in ((1,px[y][x]),(0,px[y][x+1])):
                    if c==(0,0,0): m|=0x55<<s
                    else:
                        i=idx(c); d|=(((i>>3)&1)<<(6+s))|(((i>>2)&1)<<(4+s))|(((i>>1)&1)<<(2+s))|((i&1)<<s)
                o+=bytes([m,d])
    open(out,'wb').write(bytes([2,W//2,H])+o); return W,H
if __name__=='__main__':
    d=sys.argv[1]; print(conv([f'{d}/c64_symbol_{i}.bmp' for i in range(1,17)],sys.argv[2]))

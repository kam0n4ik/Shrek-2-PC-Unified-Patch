"""Version-bound D3D8 Bink aspect-fit scaler for Shrek 2.

Preserves the existing Bink decode/timing/skip/stop path and the original black
backbuffer clear. Scales a temporary decoded frame into a centered fit rectangle.
Nearest-neighbour sampling deliberately avoids changing the user's BIK assets.
Only the D3D renderer native movie path is changed, not MovieTexture materials.
"""
from pathlib import Path
import hashlib,struct,json
import pefile,capstone
from keystone.keystone import Ks
from keystone.keystone_const import KS_ARCH_X86,KS_MODE_32

BASE=0x10000000
SITE=0x100244a5
RESUME=0x100244e7
CAVE=0x10001800
CAVE_SIZE=0x400
SHA='5ff643295ef507e399ccd4c886f9f36928f7ea43d815c58004176aa557706c61'
ORIGINAL=bytes.fromhex('8b76108b063b44243c77378b46043b442440772e8b7c24248b54241033c983ff160f95c14983e1fb83c10a81c900000080515553508b44246c525056ff1528ef1210')

ASM=r'''
pushad
sub esp, 0x40
mov ebp, esp
call getbase
getbase:
pop ebx
sub ebx, BASE_DELTA
mov esi, dword ptr [ebp+0x44]
mov esi, dword ptr [esi+0x10]
mov dword ptr [ebp+0x34], esi
mov eax, dword ptr [esi]
mov edx, dword ptr [esi+4]
test eax,eax
jle finish
test edx,edx
jle finish
cmp eax, 16384
jg finish
cmp edx, 16384
jg finish
mov dword ptr [ebp],eax
mov dword ptr [ebp+4],edx
mov ecx,4
cmp dword ptr [ebp+0x84],0x16
je bppready
cmp dword ptr [ebp+0x84],0x17
jne finish
mov ecx,2
bppready:
mov dword ptr [ebp+8],ecx
imul eax,ecx
mov dword ptr [ebp+0x28],eax
imul eax,edx
push eax
call dword ptr [ebx+0x12ee24]
add esp,4
test eax,eax
jz finish
mov dword ptr [ebp+0xc],eax
mov ecx,dword ptr [ebp+0x9c]
mov edx,dword ptr [ebp+0xa0]
test ecx,ecx
jle release
test edx,edx
jle release
cmp ecx,16384
jg release
cmp edx,16384
jg release
mov eax,ecx
imul eax,dword ptr [ebp+4]
imul edx,dword ptr [ebp]
cmp eax,edx
jle fitwidth
mov eax,dword ptr [ebp+0xa0]
mov dword ptr [ebp+0x14],eax
imul eax,dword ptr [ebp]
xor edx,edx
div dword ptr [ebp+4]
mov dword ptr [ebp+0x10],eax
jmp rectready
fitwidth:
mov dword ptr [ebp+0x10],ecx
mov eax,ecx
imul eax,dword ptr [ebp+4]
xor edx,edx
div dword ptr [ebp]
mov dword ptr [ebp+0x14],eax
rectready:
cmp dword ptr [ebp+0x10],1
jge widthready
mov dword ptr [ebp+0x10],1
widthready:
cmp dword ptr [ebp+0x14],1
jge heightready
mov dword ptr [ebp+0x14],1
heightready:
mov eax,dword ptr [ebp+0x9c]
sub eax,dword ptr [ebp+0x10]
shr eax,1
mov dword ptr [ebp+0x18],eax
imul eax,dword ptr [ebp+8]
mov ecx,dword ptr [ebp+0xa0]
sub ecx,dword ptr [ebp+0x14]
shr ecx,1
mov dword ptr [ebp+0x1c],ecx
mov edx,dword ptr [ebp+0x70]
mov dword ptr [ebp+0x24],edx
imul ecx,edx
add eax,ecx
add eax,dword ptr [ebp+0xbc]
mov dword ptr [ebp+0x20],eax
mov eax,0x80000005
cmp dword ptr [ebp+8],4
je flagsready
mov eax,0x8000000a
flagsready:
push eax
push 0
push 0
push dword ptr [ebp+4]
push dword ptr [ebp+0x28]
push dword ptr [ebp+0xc]
push dword ptr [ebp+0x34]
call dword ptr [ebx+0x12ef28]
mov dword ptr [ebp+0x3c],0
rows:
mov eax,dword ptr [ebp+0x3c]
imul eax,dword ptr [ebp+4]
xor edx,edx
div dword ptr [ebp+0x14]
imul eax,dword ptr [ebp+0x28]
add eax,dword ptr [ebp+0xc]
mov esi,eax
mov edi,dword ptr [ebp+0x20]
mov ecx,dword ptr [ebp+0x10]
xor edx,edx
cmp dword ptr [ebp+8],4
jne pixels16
pixels32:
mov eax,dword ptr [esi]
mov dword ptr [edi],eax
add edi,4
add edx,dword ptr [ebp]
advance32:
cmp edx,dword ptr [ebp+0x10]
jb next32
sub edx,dword ptr [ebp+0x10]
add esi,4
jmp advance32
next32:
dec ecx
jnz pixels32
jmp nextrow
pixels16:
mov ax,word ptr [esi]
mov word ptr [edi],ax
add edi,2
add edx,dword ptr [ebp]
advance16:
cmp edx,dword ptr [ebp+0x10]
jb next16
sub edx,dword ptr [ebp+0x10]
add esi,2
jmp advance16
next16:
dec ecx
jnz pixels16
nextrow:
mov eax,dword ptr [ebp+0x24]
add dword ptr [ebp+0x20],eax
inc dword ptr [ebp+0x3c]
mov eax,dword ptr [ebp+0x3c]
cmp eax,dword ptr [ebp+0x14]
jl rows
release:
push dword ptr [ebp+0xc]
call dword ptr [ebx+0x12ee74]
add esp,4
finish:
mov esp,ebp
add esp,0x40
popad
jmp 0x100244e7
'''

def code():
    ks=Ks(KS_ARCH_X86,KS_MODE_32)
    # getbase returns immediately after call: 1B pushad + 3B sub + 2B mov + 5B call.
    text=ASM.replace('BASE_DELTA',hex(CAVE-BASE+11))
    result=bytes(ks.asm(text,addr=CAVE)[0])
    assert len(result)<=CAVE_SIZE
    return result

def patch_bytes(raw):
    assert hashlib.sha256(raw).hexdigest()==SHA,'Unsupported D3DDrv.dll'
    pe=pefile.PE(data=raw)
    assert pe.OPTIONAL_HEADER.ImageBase==BASE
    pos=pe.get_offset_from_rva(SITE-BASE)
    cave=pe.get_offset_from_rva(CAVE-BASE)
    assert raw[pos:pos+len(ORIGINAL)]==ORIGINAL,(raw[pos:pos+len(ORIGINAL)].hex(),ORIGINAL.hex())
    assert len(ORIGINAL)==RESUME-SITE
    assert raw[cave:cave+CAVE_SIZE]==b'\xcc'*CAVE_SIZE
    assert all(not(SITE-BASE<=e.rva<SITE-BASE+5 or CAVE-BASE<=e.rva<CAVE-BASE+CAVE_SIZE)
               for block in pe.DIRECTORY_ENTRY_BASERELOC for e in block.entries)
    result=bytearray(raw)
    # Only the first five bytes are replaced. The unused original copy block
    # retains its import relocation entry, avoiding loader writes into new code.
    result[pos:pos+5]=b'\xe9'+struct.pack('<i',CAVE-SITE-5)
    result[cave:cave+len(code())]=code()
    return bytes(result)

def inventory():
    rows=[]
    for file in sorted(Path('E:/Shrek 2/Movies').glob('*.bik')):
        with file.open('rb') as stream: head=stream.read(44)
        assert head[:3]==b'BIK'
        width,height=struct.unpack_from('<II',head,20)
        rows.append({'file':file.name,'bytes':file.stat().st_size,'signature':head[:4].decode('ascii'),'width':width,'height':height})
    return rows

if __name__=='__main__':
    out=Path(__file__).parent
    raw=Path(__file__).resolve().parents[2].joinpath('original/System/D3DDrv.dll').read_bytes()
    patched=patch_bytes(raw)
    (out/'D3DDrv.movies.dll').write_bytes(patched)
    pe=pefile.PE(data=patched)
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    rows=['%08X  %-8s %s'%(i.address,i.mnemonic,i.op_str) for i in md.disasm(code(),CAVE)]
    (out/'movie-fit-code.asm').write_text('\n'.join(rows)+'\n')
    evidence={'original_sha256':SHA,'patched_sha256':hashlib.sha256(patched).hexdigest(),'site':hex(SITE),'resume':hex(RESUME),'cave':hex(CAVE),'code_bytes':len(code()),'sampling':'nearest-neighbour centered fit','movie_headers':inventory(),'runtime_gameplay_verified':False}
    (out/'movie-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k!='movie_headers'},indent=2))

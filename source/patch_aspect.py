"""Version-bound Shrek 2 camera projection patch; never writes the installed game.

The original native camera fixes horizontal FOV and uses viewport W/H as the
projection Y multiplier. For aspect > 4:3, preserve its 4:3 vertical coverage by
using X multiplier (4/3)/(W/H), and Y multiplier 4/3. Narrow and 4:3 views follow
the exact original arithmetic. Stack-only constants avoid adding PE relocations.
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import pefile
import capstone

ORIGINAL_SHA256 = '977a1595276bc87836c03f489391b98b3a4b612ba50d5e243b560365ad397b85'
BASE = 0x10300000
SITE = 0x10497f73
RESUME = 0x10497f86
CAVE = 0x1049a700
ORIGINAL = bytes.fromhex('d8 7c 24 64 8d 8c 24 88 00 00 00 d9 1c 24 68 00 00 80 3f')

def reljump(source, target):
    return b'\xe9' + struct.pack('<i', target-source-5)

def cave_code():
    out = bytearray()
    out += bytes.fromhex('d8 7c 24 64')     # A = W/H; original x87 H is input
    out += bytes.fromhex('c7 04 24 ab aa aa 3f') # reserved Y multiplier = 4/3
    out += bytes.fromhex('d9 04 24 df f1')   # compare 4/3 >= A, pop comparison
    branch = len(out)
    out += bytes.fromhex('0f 83 00 00 00 00')
    out += bytes.fromhex('d8 3c 24')         # (4/3)/A
    out += bytes.fromhex('8d 8c 24 88 00 00 00') # original matrix destination
    out += bytes.fromhex('51 d9 1c 24')     # reserve and write X multiplier
    out += reljump(CAVE+len(out), RESUME)
    original_path = len(out)
    out += bytes.fromhex('8d 8c 24 88 00 00 00 d9 1c 24 68 00 00 80 3f')
    out += reljump(CAVE+len(out), RESUME)
    struct.pack_into('<i', out, branch+2, original_path-branch-6)
    return bytes(out)

def patch_bytes(original):
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256, 'Unsupported Engine.dll'
    pe = pefile.PE(data=original)
    assert pe.OPTIONAL_HEADER.ImageBase == BASE
    site_offset = pe.get_offset_from_rva(SITE-BASE)
    cave_offset = pe.get_offset_from_rva(CAVE-BASE)
    assert original[site_offset:site_offset+len(ORIGINAL)] == ORIGINAL
    assert original[cave_offset:cave_offset+96] == b'\xcc'*96
    # The selected cave is executable padding after FCameraSceneNode's return,
    # before the next native function at 0x1049a760. No absolute pointers are new.
    assert all(not (SITE-BASE <= e.rva < RESUME-BASE or CAVE-BASE <= e.rva < CAVE-BASE+96)
               for block in pe.DIRECTORY_ENTRY_BASERELOC for e in block.entries)
    patched = bytearray(original)
    code = cave_code()
    assert len(code) <= 96
    patched[site_offset:site_offset+len(ORIGINAL)] = reljump(SITE,CAVE)+b'\x90'*(len(ORIGINAL)-5)
    patched[cave_offset:cave_offset+len(code)] = code
    return bytes(patched)

def verify_machine_code(patched):
    """Emulate the actual inserted x87 bytes, independent of the patch formula."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX
    pe = pefile.PE(data=patched)
    checks=[]
    for width,height in [(640,480),(800,600),(1024,768),(512,384),(1280,720),
                         (1366,768),(1600,900),(1920,1080),(2560,1440),(1280,1024),(600,800)]:
        uc = Uc(UC_ARCH_X86,UC_MODE_32)
        uc.mem_map(BASE,0x700000)
        uc.mem_write(BASE,pe.get_memory_mapped_image())
        uc.mem_map(0x700000,0x200000)
        uc.mem_map(0x900000,0x1000)
        uc.mem_write(0x900000,struct.pack('<f',height))
        uc.mem_write(0x900100,bytes.fromhex('d9 05 00 00 90 00')+reljump(0x900106,SITE-1))
        stack=0x800000
        uc.reg_write(UC_X86_REG_ESP,stack)
        uc.reg_write(UC_X86_REG_EAX,0x3f400000)
        uc.reg_write(UC_X86_REG_ECX,0x12345678)
        uc.mem_write(stack+0x60,struct.pack('<f',width))
        uc.hook_add(UC_HOOK_CODE,lambda emu,address,size,user: emu.emu_stop() if address == RESUME else None)
        uc.emu_start(0x900100,RESUME,count=100)
        sp=uc.reg_read(UC_X86_REG_ESP)
        x,y=struct.unpack('<ff',uc.mem_read(sp,8))
        aspect=width/height
        ex,ey=((4/3)/aspect,4/3) if aspect>4/3 else (1.,aspect)
        assert math.isclose(x,ex,rel_tol=2e-7),(width,height,x,ex)
        assert math.isclose(y,ey,rel_tol=2e-7),(width,height,y,ey)
        assert sp==stack-8
        assert uc.reg_read(UC_X86_REG_ECX)==stack+0x84
        assert uc.reg_read(UC_X86_REG_EAX)==0x3f400000
        checks.append({'width':width,'height':height,'projection_x_multiplier':x,'projection_y_multiplier':y})
    return checks

def disassembly(data,address,size):
    pe=pefile.PE(data=data)
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    return ['%08X  %-8s %s'%(i.address,i.mnemonic,i.op_str) for i in md.disasm(pe.get_data(address-BASE,size),address)]

if __name__=='__main__':
    import sys
    src=Path(sys.argv[1]) if len(sys.argv)>1 else Path(r'E:\Shrek 2\System\Engine.dll')
    out=Path(__file__).parent
    original=src.read_bytes()
    patched=patch_bytes(original)
    checks=verify_machine_code(patched)
    (out/'Engine.patched.dll').write_bytes(patched)
    evidence={'source':str(src),'original_sha256':ORIGINAL_SHA256,'patched_sha256':hashlib.sha256(patched).hexdigest(),
              'patch_site_va':hex(SITE),'code_cave_va':hex(CAVE),'code_cave_bytes':len(cave_code()),
              'before':disassembly(original,SITE,len(ORIGINAL)),
              'after_site':disassembly(patched,SITE,len(ORIGINAL)),
              'after_cave':disassembly(patched,CAVE,len(cave_code())),
              'unicorn_emulation':checks,'runtime_gameplay_verified':False}
    (out/'aspect-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence,indent=2))

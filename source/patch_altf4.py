"""Forward only genuine Alt+F4 system key-down events to the existing DefWindowProc path."""
from pathlib import Path
import struct,hashlib,json
import pefile,capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *

ROOT=Path(__file__).resolve().parent
BASE=0x11100000
SITE=0x11108dcc
RESUME=SITE+5
CAVE=0x11101500
DEFAULT=0x1110a4c2
ORIGINAL_HASH='adc511b1ad39fbe94054be7b5f5f0838a3caf81f157c4a5b1b53bde5c7039cd3'
ORIGINAL=bytes.fromhex('39 1a 89 5d fc')
def jmp(a,b):return b'\xe9'+struct.pack('<i',b-a-5)

def cave_code():
    out=bytearray()
    out+=bytes.fromhex('81 7d 08 04 01 00 00') # uMsg == WM_SYSKEYDOWN
    first=len(out);out+=b'\x75\0'
    out+=bytes.fromhex('83 7d 0c 73') # wParam == VK_F4
    second=len(out);out+=b'\x75\0'
    out+=bytes.fromhex('f7 45 10 00 00 00 20') # lParam's ALT context bit 29
    third=len(out);out+=b'\x74\0'
    out+=bytes.fromhex('8b 45 08 8b 55 ec') # normal default path expects message and viewport
    out+=jmp(CAVE+len(out),DEFAULT)
    fallback=len(out)
    out+=ORIGINAL+jmp(CAVE+len(out)+len(ORIGINAL),RESUME)
    for p in [first,second,third]:out[p+1]=fallback-(p+2)
    assert len(out)<=48
    return bytes(out)

def patch_bytes(original):
    assert hashlib.sha256(original).hexdigest()==ORIGINAL_HASH,'Unsupported WinDrv.dll'
    pe=pefile.PE(data=original)
    so=pe.get_offset_from_rva(SITE-BASE);co=pe.get_offset_from_rva(CAVE-BASE)
    assert original[so:so+5]==ORIGINAL
    assert original[co:co+48]==b'\xcc'*48
    assert pe.get_section_by_rva(CAVE-BASE).Characteristics&0x20000000
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for e in block.entries:
            assert not (SITE-BASE<=e.rva<SITE-BASE+5 or CAVE-BASE<=e.rva<CAVE-BASE+48)
    code=cave_code();patched=bytearray(original)
    patched[so:so+5]=jmp(SITE,CAVE)
    patched[co:co+len(code)]=code
    return bytes(patched)

def verify(patched):
    results=[]
    for load_base in [BASE,0x22100000]:
        pe=pefile.PE(data=patched);pe.relocate_image(load_base)
        delta=load_base-BASE
        uc=Uc(UC_ARCH_X86,UC_MODE_32)
        uc.mem_map(load_base,0x100000);uc.mem_write(load_base,pe.get_memory_mapped_image())
        uc.mem_map(0x700000,0x30000)
        stopped=[]
        def stop(emu,address,size,user):
            if address in [RESUME+delta,DEFAULT+delta]:stopped.append(address-delta);emu.emu_stop()
        uc.hook_add(UC_HOOK_CODE,stop)
        count=0
        for message in [0x100,0x104]:
            for key in range(256):
                for alt in [False,True]:
                    for editor in [0,1]:
                        stopped.clear()
                        ebp=0x710000;viewport=0x720000;editorptr=0x720100
                        uc.mem_write(ebp+8,struct.pack('<III',message,key,0x20000000 if alt else 0))
                        uc.mem_write(ebp-0x14,struct.pack('<I',viewport))
                        uc.mem_write(ebp-4,b'\x7f'*4)
                        uc.mem_write(editorptr,struct.pack('<I',editor))
                        regs={UC_X86_REG_EBP:ebp,UC_X86_REG_ESP:ebp-0x400,UC_X86_REG_EAX:message,
                              UC_X86_REG_EBX:0,UC_X86_REG_ECX:0x13572468,UC_X86_REG_EDX:editorptr,
                              UC_X86_REG_ESI:0x12345678,UC_X86_REG_EDI:0x23456789,UC_X86_REG_EFLAGS:0x202}
                        for reg,value in regs.items():uc.reg_write(reg,value)
                        uc.emu_start(SITE+delta,load_base+0x100000,count=50)
                        match=message==0x104 and key==0x73 and alt
                        assert stopped==[DEFAULT if match else RESUME],(message,key,alt,editor,stopped)
                        for reg in [UC_X86_REG_EBP,UC_X86_REG_ESP,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_ESI,UC_X86_REG_EDI]:
                            assert uc.reg_read(reg)==regs[reg]
                        if match:
                            assert uc.reg_read(UC_X86_REG_EDX)==viewport
                            assert uc.reg_read(UC_X86_REG_EAX)==message
                        else:
                            assert uc.reg_read(UC_X86_REG_EDX)==editorptr
                            assert bool(uc.reg_read(UC_X86_REG_EFLAGS)&0x40)==(editor==0)
                            assert uc.mem_read(ebp-4,4)==b'\0'*4
                        count+=1
        results.append({'load_base':hex(load_base),'message_key_alt_editor_combinations_passed':count})
    return results

if __name__=='__main__':
    src=ROOT.parent/'original/System/WinDrv.dll'
    src.parent.mkdir(parents=True,exist_ok=True)
    if not src.exists():src.write_bytes(Path('E:/Shrek 2/System/WinDrv.dll').read_bytes())
    original=src.read_bytes();patched=patch_bytes(original);checks=verify(patched)
    (ROOT/'WinDrv.patched.dll').write_bytes(patched)
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    pe=pefile.PE(data=patched)
    code=cave_code()
    report={'original_sha256':ORIGINAL_HASH,'patched_sha256':hashlib.sha256(patched).hexdigest(),
            'site_va':hex(SITE),'site_offset':pe.get_offset_from_rva(SITE-BASE),
            'cave_va':hex(CAVE),'cave_offset':pe.get_offset_from_rva(CAVE-BASE),'cave_length':len(code),
            'original_hook_bytes':ORIGINAL.hex(' '),'new_hook_bytes':pe.get_data(SITE-BASE,5).hex(' '),
            'cave_assembly':['%08X  %s %s'%(i.address,i.mnemonic,i.op_str) for i in md.disasm(code,CAVE)],
            'emulation':checks,'actual_keyboard_runtime_test':False,
            'cause':'WM_KEYDOWN (0x100) and WM_SYSKEYDOWN (0x104) share handler 0x11108DC6; in non-editor mode it consumes both and returns without DefWindowProc. Only Alt+Enter has a special path. VK_F4 has no special case.',
            'fix':'At the shared handler, forward WM_SYSKEYDOWN + VK_F4 + ALT-context-bit to the existing ANSI/Unicode DefWindowProc path; all other keys execute the original instructions.'}
    (ROOT/'altf4-evidence.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

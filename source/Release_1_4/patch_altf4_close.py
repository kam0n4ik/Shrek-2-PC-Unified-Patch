"""Alt+F4 -> WM_CLOSE through the viewport's existing DefWindowProc path.

Codex 1.3 forwarded WM_SYSKEYDOWN/VK_F4 to DefWindowProc; Windows turned it into
SC_CLOSE but dropped it because the fullscreen window has no WS_SYSMENU
(style 0x14000000), so WM_CLOSE never arrived. A posted WM_CLOSE was verified
live to shut the game down normally, so Alt+F4 now becomes WM_CLOSE directly.
"""
from pathlib import Path
import struct, hashlib, json, sys
import pefile, capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

BASE = 0x11100000
SITE = 0x11108dcc
RESUME = SITE + 5
CAVE = 0x11101500
DEFAULT = 0x1110a4c2
ORIGINAL_HASH = 'adc511b1ad39fbe94054be7b5f5f0838a3caf81f157c4a5b1b53bde5c7039cd3'
ORIGINAL = bytes.fromhex('39 1a 89 5d fc')
CAVE_LEN = 48


def jmp(a, b):
    return b'\xe9' + struct.pack('<i', b - a - 5)


def cave_code():
    out = bytearray()
    out += bytes.fromhex('3d 04 01 00 00')            # cmp eax, WM_SYSKEYDOWN
    j1 = len(out); out += b'\x75\0'
    out += bytes.fromhex('83 7d 0c 73')               # cmp wParam, VK_F4
    j2 = len(out); out += b'\x75\0'
    out += bytes.fromhex('f6 45 13 20')               # test lParam bit 29 (ALT context)
    j3 = len(out); out += b'\x74\0'
    out += bytes.fromhex('31 c0')                     # xor eax, eax
    out += bytes.fromhex('89 45 0c')                  # wParam = 0
    out += bytes.fromhex('89 45 10')                  # lParam = 0
    out += bytes.fromhex('b0 10')                     # eax = WM_CLOSE
    out += bytes.fromhex('8b 55 ec')                  # edx = viewport
    out += jmp(CAVE + len(out), DEFAULT)
    fb = len(out)
    out += ORIGINAL + jmp(CAVE + len(out) + len(ORIGINAL), RESUME)
    for p in (j1, j2, j3):
        out[p + 1] = fb - (p + 2)
    assert len(out) <= CAVE_LEN, len(out)
    return bytes(out)


def patch_bytes(original):
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_HASH, 'Unsupported WinDrv.dll'
    pe = pefile.PE(data=original)
    so = pe.get_offset_from_rva(SITE - BASE); co = pe.get_offset_from_rva(CAVE - BASE)
    assert original[so:so + 5] == ORIGINAL
    assert original[co:co + CAVE_LEN] == b'\xcc' * CAVE_LEN
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for e in block.entries:
            assert not (SITE - BASE <= e.rva < SITE - BASE + 5 or CAVE - BASE <= e.rva < CAVE - BASE + CAVE_LEN)
    code = cave_code(); patched = bytearray(original)
    patched[so:so + 5] = jmp(SITE, CAVE)
    patched[co:co + len(code)] = code
    return bytes(patched)


def verify(patched):
    results = []
    for load_base in [BASE, 0x22100000]:
        pe = pefile.PE(data=patched); pe.relocate_image(load_base)
        delta = load_base - BASE
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(load_base, 0x100000); uc.mem_write(load_base, pe.get_memory_mapped_image())
        uc.mem_map(0x700000, 0x30000)
        stopped = []
        def stop(emu, address, size, user):
            if address in [RESUME + delta, DEFAULT + delta]:
                stopped.append(address - delta); emu.emu_stop()
        uc.hook_add(UC_HOOK_CODE, stop)
        count = 0
        for message in [0x100, 0x104]:
            for key in range(256):
                for alt in [False, True]:
                    for editor in [0, 1]:
                        stopped.clear()
                        ebp = 0x710000; viewport = 0x720000; editorptr = 0x720100
                        lparam = 0x003e0001 | (0x20000000 if alt else 0)
                        uc.mem_write(ebp + 8, struct.pack('<III', message, key, lparam))
                        uc.mem_write(ebp - 0x14, struct.pack('<I', viewport))
                        uc.mem_write(ebp - 4, b'\x7f' * 4)
                        uc.mem_write(editorptr, struct.pack('<I', editor))
                        regs = {UC_X86_REG_EBP: ebp, UC_X86_REG_ESP: ebp - 0x400, UC_X86_REG_EAX: message,
                                UC_X86_REG_EBX: 0, UC_X86_REG_ECX: 0x13572468, UC_X86_REG_EDX: editorptr,
                                UC_X86_REG_ESI: 0x12345678, UC_X86_REG_EDI: 0x23456789, UC_X86_REG_EFLAGS: 0x202}
                        for reg, value in regs.items():
                            uc.reg_write(reg, value)
                        uc.emu_start(SITE + delta, load_base + 0x100000, count=50)
                        match = message == 0x104 and key == 0x73 and alt
                        assert stopped == [DEFAULT if match else RESUME], (message, key, alt, editor, stopped)
                        for reg in [UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI]:
                            assert uc.reg_read(reg) == regs[reg]
                        if match:
                            assert uc.reg_read(UC_X86_REG_EAX) == 0x10
                            assert uc.reg_read(UC_X86_REG_EDX) == viewport
                            assert uc.mem_read(ebp + 0xc, 8) == b'\0' * 8
                        else:
                            assert uc.reg_read(UC_X86_REG_EAX) == message
                            assert uc.reg_read(UC_X86_REG_ECX) == regs[UC_X86_REG_ECX]
                            assert uc.reg_read(UC_X86_REG_EDX) == editorptr
                            assert bool(uc.reg_read(UC_X86_REG_EFLAGS) & 0x40) == (editor == 0)
                            assert uc.mem_read(ebp - 4, 4) == b'\0' * 4
                            assert uc.mem_read(ebp + 8, 12) == struct.pack('<III', message, key, lparam)
                        count += 1
        results.append({'load_base': hex(load_base), 'combinations_passed': count})
    return results


if __name__ == '__main__':
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    original = src.read_bytes(); patched = patch_bytes(original); checks = verify(patched)
    dst.write_bytes(patched)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    print(json.dumps({'patched_sha256': hashlib.sha256(patched).hexdigest(), 'cave_len': len(cave_code()),
                      'emulation': checks,
                      'asm': ['%08X  %s %s' % (i.address, i.mnemonic, i.op_str) for i in md.disasm(cave_code(), CAVE)]}, indent=1))

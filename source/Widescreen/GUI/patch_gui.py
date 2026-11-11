"""GUI-only 4:3, height-based layout inside a widescreen viewport.

Never changes the installed game. No viewport/Canvas size mutation or mouse
coordinate mutation is used. Geometry and hit-test bounds share ActualXX.
"""
from pathlib import Path
import struct,math,json,hashlib
import pefile,capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parent
ORIGINAL_SHA256='8a964d576f315ddc6a3bbcf4b86d44c36a7d86ae70a350f7bf78a75f38fe7e08'
BASE=0x10000000
CAVE=BASE+0x3000
WIDTH_SITE=BASE+0x1a7fc
LEFT_SITE=BASE+0x1aabe
FONT_SITE=BASE+0x19bcb

class Asm:
    def __init__(self,base):self.base=base;self.d=bytearray();self.labels={};self.fix=[]
    def add(self,h):self.d+=bytes.fromhex(h);return self
    def label(self,s):self.labels[s]=len(self.d);return self
    def jcc(self,opcode,label):self.fix.append((len(self.d)+1,label));self.d+=bytes([opcode,0]);return self
    def jump(self,address):self.d+=b'\xe9'+struct.pack('<i',address-(self.base+len(self.d)+5));return self
    def call(self,address):self.d+=b'\xe8'+struct.pack('<i',address-(self.base+len(self.d)+5));return self
    def done(self):
        for p,s in self.fix:
            delta=self.labels[s]-(p+1);assert -128<=delta<=127;self.d[p]=delta&255
        return bytes(self.d)

def width_helper(address):
    a=Asm(address)
    # EDX = the already-validated UViewport*. Preserve registers and CPU flags;
    # return one FPU value, exactly as the replaced FILD instruction did.
    a.add('9c 50 51 8b 82 8c 00 00 00 8b 8a 90 00 00 00')
    a.add('8d 04 40 c1 e1 02 39 c8').jcc(0x76,'narrow')
    a.add('51 db 04 24 c7 04 24 03 00 00 00 da 34 24 83 c4 04').jcc(0xeb,'end')
    a.label('narrow').add('db 82 8c 00 00 00')
    a.label('end').add('59 58 9d c3')
    return a.done()

def left_helper(address,width_address):
    a=Asm(address)
    a.add('9c').call(width_address)
    # V = min(W, 4H/3). P = V * WinLeft + (W - V)/2.
    a.add('d9 c0 d8 4e 74 d9 c9 d9 e0 da 82 8c 00 00 00')
    a.add('6a 02 da 34 24 83 c4 04 de c1 9d').jump(LEFT_SITE+9)
    return a.done()

def font_helper(address):
    a=Asm(address)
    # After parsing GUIFont.GetFont(Canvas, XRes), cap only the resolution used
    # to select a font. The physical Canvas and viewport fields stay intact.
    a.add('9c 50 51 52 8b 45 ec 85 c0').jcc(0x74,'done')
    a.add('8b 40 68 c1 e0 02 33 d2 b9 03 00 00 00 f7 f1')
    a.add('3b 45 e8').jcc(0x7d,'done').add('89 45 e8')
    a.label('done').add('5a 59 58 9d 8a 43 3c 33 f6').jump(FONT_SITE+5)
    return a.done()

def branch(source,target,call=False,length=5):
    return bytes([0xe8 if call else 0xe9])+struct.pack('<i',target-source-5)+b'\x90'*(length-5)

def incoming_references(original,pe,lo,hi):
    pointers=[];branches=[]
    for off in range(len(original)-3):
        value=struct.unpack_from('<I',original,off)[0]
        if lo<=value<hi:pointers.append((off,value))
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    md.detail=True;md.skipdata=True
    for section in pe.sections:
        if not section.Characteristics&0x20000000:continue
        for instruction in md.disasm(section.get_data(),BASE+section.VirtualAddress):
            if instruction.id==0:continue
            if instruction.mnemonic=='call' or instruction.mnemonic.startswith('j'):
                ops=instruction.operands
                if ops and ops[0].type==capstone.x86.X86_OP_IMM and lo<=ops[0].imm<hi:
                    branches.append((instruction.address,ops[0].imm))
    return {'absolute_pointer_candidates':pointers,'direct_incoming_branches':branches,
            'scope':'Raw pointer scan and linear executable-section direct-branch scan; arbitrary computed indirect references are not proven absent.'}

def patch_bytes(original):
    assert hashlib.sha256(original).hexdigest()==ORIGINAL_SHA256,'Unsupported GUI.dll build'
    pe=pefile.PE(data=original)
    assert pe.OPTIONAL_HEADER.ImageBase==BASE
    # Exact bytes and the file hash are both bound below by the caller.
    assert pe.get_data(WIDTH_SITE-BASE,6)==bytes.fromhex('db 82 8c 00 00 00')
    assert pe.get_data(LEFT_SITE-BASE,9)==bytes.fromhex('db 82 8c 00 00 00 d8 4e 74')
    assert pe.get_data(FONT_SITE-BASE,5)==bytes.fromhex('8a 43 3c 33 f6')
    width=width_helper(CAVE)
    left_va=(CAVE+len(width)+15)&~15
    left=left_helper(left_va,CAVE)
    font_va=(left_va+len(left)+15)&~15
    font=font_helper(font_va)
    payload=bytearray(b'\xcc'*(font_va+len(font)-CAVE))
    payload[:len(width)]=width
    payload[left_va-CAVE:left_va-CAVE+len(left)]=left
    payload[font_va-CAVE:]=font
    cave_offset=pe.get_offset_from_rva(CAVE-BASE)
    assert original[cave_offset:cave_offset+len(payload)]==b'\xcc'*len(payload)
    spans=[(WIDTH_SITE,6),(LEFT_SITE,9),(FONT_SITE,5),(CAVE,len(payload))]
    relocations=[x.rva+BASE for block in pe.DIRECTORY_ENTRY_BASERELOC for x in block.entries if x.type!=0]
    assert not any(a<=r<a+n for a,n in spans for r in relocations)
    assert not any(a<=BASE+e.address<a+n for a,n in [(CAVE,len(payload))] for e in pe.DIRECTORY_ENTRY_EXPORT.symbols)
    references=incoming_references(original,pe,CAVE,CAVE+len(payload))
    assert not references['absolute_pointer_candidates'] and not references['direct_incoming_branches']
    patched=bytearray(original)
    for va,data in [(WIDTH_SITE,branch(WIDTH_SITE,CAVE,True,6)),(LEFT_SITE,branch(LEFT_SITE,left_va,False,9)),(FONT_SITE,branch(FONT_SITE,font_va)),(CAVE,payload)]:
        off=pe.get_offset_from_rva(va-BASE);patched[off:off+len(data)]=data
    return bytes(patched),{'width_helper':CAVE,'left_helper':left_va,'font_helper':font_va,'payload_bytes':len(payload),'spans':spans,'original_cave_reference_scan':references}

def resolve(pe,match):
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    e=next(e for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if match in (e.name or b'').decode())
    image_base=pe.OPTIONAL_HEADER.ImageBase
    a=image_base+e.address
    i=next(md.disasm(pe.get_data(a-image_base,8),a))
    return int(i.op_str,16) if i.mnemonic=='jmp' else a

def geometry_case(patched,w,h,nested,winleft=.25,winwidth=.2,load_base=BASE):
    pe=pefile.PE(data=patched)
    if load_base!=BASE:pe.relocate_image(load_base)
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(load_base,0x80000);uc.mem_write(load_base,pe.get_memory_mapped_image())
    uc.mem_map(0,0x1000);uc.mem_map(0x200000,0x10000)
    uc.mem_map(0x800000,0x10000);uc.mem_map(0x900000,0x10000)
    def i(a,v):uc.mem_write(a,struct.pack('<I',v))
    def f(a,v):uc.mem_write(a,struct.pack('<f',v))
    comp=0x200000;parent=0x207000;vt=0x208000
    for a,v in [(comp+0x2c,0x201000),(parent+0x2c,0x201000),(0x201000+0x34,0x202000),
                (0x202000+0x2c,0x203000),(0x203000+0x34,0x204000),(0x203000+0x30,0x205000),(0x205000,0x206000)]:i(a,v)
    i(0x206000+0x8c,w);i(0x206000+0x90,h)
    for obj in [comp,parent]:i(obj,vt)
    names={0x7c:'?ActualWidth@UGUIComponent',0x80:'?ActualHeight@UGUIComponent',0x84:'?ActualLeft@UGUIComponent',0x88:'?ActualTop@UGUIComponent'}
    for vtoff,name in names.items():i(vt+vtoff,resolve(pe,name))
    f(parent+0x74,0.);f(parent+0x78,1.);f(parent+0x70,0.);f(parent+0x7c,1.)
    uc.mem_write(comp+0x5c,bytes([3 if nested else 0]))
    if nested:i(comp+0x30,parent)
    f(comp+0x74,winleft);f(comp+0x78,winwidth);f(comp+0x70,.2);f(comp+0x7c,.1)
    i(0x808000,0x900000)
    uc.reg_write(UC_X86_REG_ESP,0x808000);uc.reg_write(UC_X86_REG_ECX,comp);uc.reg_write(UC_X86_REG_FPCW,0x37f)
    uc.emu_start(resolve(pe,'?UpdateBounds@UGUIComponent'),0x900000,count=2000)
    bounds=struct.unpack('<4f',uc.mem_read(comp+0xa8,16))
    effective=min(w,4*h/3);offset=(w-effective)/2
    expected=(offset+effective*winleft,h*.2,offset+effective*(winleft+winwidth),h*.3)
    for x,y in zip(bounds,expected):assert math.isclose(x,y,abs_tol=.0005),(w,h,nested,bounds,expected)
    # GUI script hit-tests use the same stored physical Bounds. Check a point
    # inside the visual rectangle and one just outside its physical left edge.
    inside=((bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2)
    assert bounds[0]<=inside[0]<=bounds[2] and bounds[1]<=inside[1]<=bounds[3]
    outside=(bounds[0]-.5,inside[1]);assert not(bounds[0]<=outside[0]<=bounds[2])
    return {'width':w,'height':h,'nested_parent':nested,'load_base':hex(load_base),'bounds':bounds,'effective_width':effective,'offset_x':offset}

def font_case(patched,info,w,h,load_base=BASE):
    pe=pefile.PE(data=patched);uc=Uc(UC_ARCH_X86,UC_MODE_32)
    if load_base!=BASE:pe.relocate_image(load_base)
    uc.mem_map(load_base,0x80000);uc.mem_write(load_base,pe.get_memory_mapped_image())
    uc.mem_map(0x200000,0x10000);uc.mem_map(0x800000,0x10000)
    frame=0x808000;stack=0x807000;canvas=0x200000;font=0x201000
    def i(a,v):uc.mem_write(a,struct.pack('<I',v))
    i(frame-0x14,canvas);i(frame-0x18,w);i(canvas+0x64,w);i(canvas+0x68,h)
    uc.mem_write(font+0x3c,b'\xa5')
    values={UC_X86_REG_ESP:stack,UC_X86_REG_EBP:frame,UC_X86_REG_EAX:0x12345678,UC_X86_REG_ECX:0x98765432,UC_X86_REG_EDX:0x11223344,UC_X86_REG_EBX:font,UC_X86_REG_ESI:0x55667788}
    for reg,v in values.items():uc.reg_write(reg,v)
    site=FONT_SITE+load_base-BASE
    uc.emu_start(site,site+5,count=500)
    expected=min(w,4*h//3)
    actual=struct.unpack('<I',uc.mem_read(frame-0x18,4))[0]
    assert actual==expected
    assert struct.unpack('<II',uc.mem_read(canvas+0x64,8))==(w,h),'Canvas dimensions mutated'
    assert uc.reg_read(UC_X86_REG_ESP)==stack
    for reg in [UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX]:assert uc.reg_read(reg)==values[reg]
    assert uc.reg_read(UC_X86_REG_EAX)==0x123456a5 and uc.reg_read(UC_X86_REG_ESI)==0
    return {'width':w,'height':h,'load_base':hex(load_base),'font_resolution':actual,'canvas_unchanged':True}

def main():
    original=Path('E:/Shrek 2/System/GUI.dll').read_bytes()
    digest=hashlib.sha256(original).hexdigest()
    assert digest==ORIGINAL_SHA256,'Unsupported GUI.dll build'
    patched,info=patch_bytes(original)
    sizes=[(640,480),(800,600),(1024,768),(1280,720),(1366,768),(1600,900),(1920,1080),(2560,1440),(1280,1024),(600,800)]
    geometry=[geometry_case(patched,w,h,n,load_base=load_base) for load_base in [BASE,0x20000000] for w,h in sizes for n in [False,True]]
    fonts=[font_case(patched,info,w,h,load_base=load_base) for load_base in [BASE,0x20000000] for w,h in sizes]
    (ROOT/'GUI.patched.dll').write_bytes(patched)
    pe=pefile.PE(data=patched);md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    def dis(a,n):return ['%08X  %-8s %s'%(x.address,x.mnemonic,x.op_str) for x in md.disasm(pe.get_data(a-BASE,n),a)]
    evidence={'original_sha256':digest,'patched_sha256':hashlib.sha256(patched).hexdigest(),**info,
              'file_spans':[{'offset':pe.get_offset_from_rva(a-BASE),'length':n} for a,n in info['spans']],
              'geometry_emulation':geometry,'font_emulation':fonts,
              'helpers':dis(CAVE,info['payload_bytes']),
              'runtime_menu_verified':False,
              'scope':'GUI component geometry, shared hit-test Bounds, and GUI font resolution selection only. World viewport, Canvas dimensions, mouse coordinates, absolute unbound pixel coordinates, and height math are unchanged.'}
    (ROOT/'gui-aspect-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sha256':digest,'patched_sha256':evidence['patched_sha256'],'geometry_cases':len(geometry),'font_cases':len(fonts),'payload_bytes':info['payload_bytes']}))

if __name__=='__main__':main()

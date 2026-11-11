from pathlib import Path
import struct,json,time
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
from patch_movies import patch_bytes,BASE,SITE,RESUME,inventory

REGS=[UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP]

def run(sw,sh,w,h,bpp=4,rebase=BASE,do_pixels=True,malloc_fail=False,source=None):
    raw=Path(__file__).resolve().parents[2].joinpath('original/System/D3DDrv.dll').read_bytes()
    patched=patch_bytes(raw)
    pe=pefile.PE(data=patched)
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(rebase,0x140000)
    uc.mem_write(rebase,pe.get_memory_mapped_image())
    uc.mem_map(0x300000,0x1000)
    uc.mem_map(0x3f0000,0x20000)
    uc.mem_map(0x500000,0x20000)
    pitch=w*bpp+16
    dest_size=pitch*h
    uc.mem_map(0x600000,((dest_size+0x2000)//0x1000)*0x1000)
    frame_size=sw*sh*bpp
    uc.mem_map(0x2000000,((frame_size+0x2000)//0x1000)*0x1000)
    stack=0x400000
    obj,bink,dest,temp=0x500000,0x510000,0x600100,0x2000100
    write32=lambda a,n:uc.mem_write(a,struct.pack('<I',n))
    read32=lambda a:struct.unpack('<I',uc.mem_read(a,4))[0]
    write32(obj+0x10,bink)
    write32(bink,sw);write32(bink+4,sh)
    # Use the actual formats selected by this D3D8 renderer, as independently
    # observed in its SetRes and original Bink copy path: X8R8G8B8=22, R5G6B5=23.
    for offset,n in [(0x10,pitch),(0x24,0x17 if bpp==2 else 0x16),(0x3c,w),(0x40,h),(0x5c,dest)]:write32(stack+offset,n)
    uc.mem_write(dest-0x100,b'\xdd'*0x100)
    uc.mem_write(dest+dest_size,b'\xdd'*0x100)
    uc.mem_write(temp-0x100,b'\xcc'*0x100)
    uc.mem_write(temp+frame_size,b'\xcc'*0x100)
    if source is None:
        source=b''.join((0x1000+x+y*sw).to_bytes(bpp,'little') for y in range(sh) for x in range(sw))
    assert len(source)==frame_size
    calls=[]
    def stub(emu,address,size,user):
        sp=emu.reg_read(UC_X86_REG_ESP);ret=read32(sp)
        if address==0x300000:
            n=read32(sp+4);assert n==frame_size
            emu.reg_write(UC_X86_REG_EAX,0 if malloc_fail else temp)
            calls.append('malloc')
            cleanup=4
        elif address==0x300100:
            assert read32(sp+4)==temp
            calls.append('free');cleanup=4
        else:
            args=[read32(sp+4+i*4) for i in range(7)]
            assert args==[bink,temp,sw*bpp,sh,0,0,0x8000000a if bpp==2 else 0x80000005],args
            calls.append('BinkCopyToBuffer')
            if do_pixels:emu.mem_write(temp,source)
            cleanup=32
        emu.reg_write(UC_X86_REG_ESP,sp+cleanup)
        emu.reg_write(UC_X86_REG_EIP,ret)
    for address in [0x300000,0x300100,0x300200]:uc.hook_add(UC_HOOK_CODE,stub,begin=address,end=address)
    write32(rebase+0x12ee24,0x300000)
    write32(rebase+0x12ee74,0x300100)
    write32(rebase+0x12ef28,0x300200)
    originals=[0x12345678,0x76543210,0x11223344,0x55667788,obj,0x99887766,0x7b]
    for reg,n in zip(REGS,originals):uc.reg_write(reg,n)
    uc.reg_write(UC_X86_REG_ESP,stack)
    resume=rebase+RESUME-BASE
    stop_address=resume
    if not do_pixels:
        # Capture the completed destination rectangle just before Bink decoding.
        from patch_movies import code,CAVE
        import capstone
        md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
        addr=next(i.address for i in md.disasm(code(),CAVE) if i.mnemonic=='call' and '0x12ef28' in i.op_str)
        stop_address=rebase+addr-BASE
    uc.hook_add(UC_HOOK_CODE,lambda emu,a,s,u:emu.emu_stop(),begin=stop_address,end=stop_address)
    began=time.perf_counter()
    uc.emu_start(rebase+SITE-BASE,stop_address,count=150000000)
    elapsed=time.perf_counter()-began
    frame=stack-0x60
    dw,dh,left,top=[read32(frame+off) for off in [0x10,0x14,0x18,0x1c]]
    expected=(w,max(1,w*sh//sw)) if w*sh<=h*sw else (max(1,h*sw//sh),h)
    if not malloc_fail:
        assert (dw,dh)==expected,(dw,dh,expected)
        assert (left,top)==((w-dw)//2,(h-dh)//2)
    if do_pixels:
        assert [uc.reg_read(r) for r in REGS]==originals
        assert uc.reg_read(UC_X86_REG_ESP)==stack
        assert uc.mem_read(dest-0x100,0x100)==b'\xdd'*0x100
        assert uc.mem_read(dest+dest_size,0x100)==b'\xdd'*0x100
        assert uc.mem_read(temp-0x100,0x100)==b'\xcc'*0x100
        assert uc.mem_read(temp+frame_size,0x100)==b'\xcc'*0x100
        output=bytes(uc.mem_read(dest,dest_size))
        if malloc_fail:
            assert output==b'\0'*len(output)
            assert calls==['malloc']
        else:
            assert calls==['malloc','BinkCopyToBuffer','free']
            for y in range(h):
                row=output[y*pitch:(y+1)*pitch]
                if top<=y<top+dh:
                    sy=(y-top)*sh//dh
                    ref=b''.join(source[(sy*sw+(x*sw//dw))*bpp:(sy*sw+(x*sw//dw)+1)*bpp] for x in range(dw))
                    assert row==b'\0'*(left*bpp)+ref+b'\0'*(pitch-(left+dw)*bpp),(sw,sh,w,h,y)
                else:assert row==b'\0'*pitch
        result={'source':[sw,sh],'target':[w,h],'bpp':bpp,'rebase':hex(rebase),'rect':[left,top,dw,dh],'full_pixel_comparison':True,'malloc_failure':malloc_fail,'elapsed_emulation_seconds':round(elapsed,3)}
        return result,output,pitch
    return {'source':[sw,sh],'target':[w,h],'bpp':bpp,'rect':[left,top,dw,dh],'full_pixel_comparison':False},None,pitch

if __name__=='__main__':
    checks=[]
    for args in [(4,3,16,9,4),(16,12,8,4,4),(4,3,6,10,4),(4,3,16,9,2),(4,3,4,3,4)]:
        checks.append(run(*args)[0])
    checks.append(run(4,3,16,9,rebase=0x20000000)[0])
    checks.append(run(4,3,16,9,malloc_fail=True)[0])
    for sw,sh in [(512,384),(640,480),(800,600),(1024,768)]:
        for w,h in [(1280,720),(1366,768),(1600,900),(1920,1080),(2560,1440),(1024,768)]:
            checks.append(run(sw,sh,w,h,do_pixels=False)[0])
    result={'machine_code_tests':checks,'pixel_comparisons_passed':7,'rectangle_cases_passed':24,'live_game_verified':False}
    (Path(__file__).parent/'movie-emulation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'pixel_cases':7,'rectangle_cases':24,'status':'passed'}))

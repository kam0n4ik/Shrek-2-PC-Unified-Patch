"""Scoped 4:3 HUD safe area. Only writes workspace copies; no install side effects."""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path
from dataclasses import dataclass

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
sys.path.insert(0, str(WORK))
from uepkg import Package, ci, enc_ci

@dataclass
class Code:
    d: bytes = b''
    m: int = 0
    def __add__(self, other): return Code(self.d+other.d, self.m+other.m)
    def __radd__(self, other): return self if other == 0 else NotImplemented

def raw(b): return Code(bytes(b), len(b))
def op(b): return raw([b])
def ref(n): return Code(enc_ci(n), 4)
def inst(n): return op(1)+ref(n)
def local(n): return op(0)+ref(n)
def floating(v): return raw(b'\x1e'+struct.pack('<f', v))
def cast(n, c): return raw([0x39, n])+c
def native(n, *args):
    return (op(n) if 0x70 <= n < 256 else raw([0x60+(n>>8), n&255]))+sum(args, Code())+op(0x16)
def ctx(obj, expr, typ=0): return op(0x19)+obj+raw(struct.pack('<HB', expr.m, typ))+expr
def assign(lhs, rhs): return op(0x0f)+lhs+rhs

class Function:
    def __init__(self, package, path, token_file=None):
        self.p=package
        self.exp=next(e for e in package.exports if package.full(e['index'])==path)
        self.raw=package.raw(self.exp)
        self.meta=json.loads((HERE/'tokens'/(token_file or (path+'.json'))).read_text())
        self.tokens=self.meta['tokens'];self.off=self.meta['offset'];self.size=self.meta['size']
        self.code=self.raw[self.off:self.off+self.size]
        self.mem=max(t['Position']+t['Size'] for t in self.tokens)
        self.bound={t['Position']:t['StoragePosition'] for t in self.tokens}
        # Extended native prefixes count in memory, but UELib reports storage at their low byte.
        for i,t in enumerate(self.tokens):
            sp=t['StoragePosition']
            if t['type']=='NativeFunctionToken' and self.tokens[i+1]['Position']-t['Position']==2:
                assert 0x60 <= self.code[sp-1] < 0x70
                self.bound[t['Position']]=sp-1
        self.bound[self.mem]=self.size
    def slice(self,a,b): return Code(self.code[self.bound[a]:self.bound[b]],b-a)
    def replaced(self, changes):
        changes=sorted(changes, key=lambda c:c[0])
        for (a,b,c),(d,e,f) in zip(changes,changes[1:]): assert b<=d
        def mapping(m):
            delta=0
            for a,b,c in changes:
                if m<a:return m+delta
                if m==a:return a+delta
                if a<m<b:raise ValueError(f'Offset {m} inside replaced range {a}:{b}')
                delta+=c.m-(b-a)
            return m+delta
        code=bytearray(self.code)
        for t in self.tokens:
            m=t['Position'];p=self.bound[m]
            if any(a<=m<b for a,b,c in changes):continue
            if 'CodeOffset' in t and t['CodeOffset']!=65535:
                assert t['type'] in ['JumpToken','JumpIfNotToken','CaseToken']
                struct.pack_into('<H',code,p+1,mapping(t['CodeOffset']))
            if t['type']=='ContextToken':
                child=next(x for x in self.tokens if x['Position']==m+1)
                skip_p=p+1+child['StorageSize']
                child_end=m+1+child['Size']+3
                total_end=m+t['Size']
                if any(child_end<=a and b<=total_end for a,b,c in changes):
                    struct.pack_into('<H',code,skip_p,mapping(total_end)-mapping(child_end))
        out=Code();last=0
        for a,b,c in changes:
            out+=Code(bytes(code[self.bound[last]:self.bound[a]]),a-last)+c;last=b
        return out+Code(bytes(code[self.bound[last]:]),self.mem-last)
    def serialize(self,code):
        head=bytearray(self.raw[:self.off]);struct.pack_into('<i',head,self.off-4,code.m)
        return bytes(head)+code.d+self.raw[self.off+self.size:]

class Builder:
    def __init__(self, path):
        self.p=Package(path);self.changed={};self.table=[dict(e) for e in self.p.exports]
        self.names=list(self.p.names);self.new_names=[];self.new_imports=[];self.new_exports=[];self.notes=[]
    def obj(self,path):
        for e in self.p.imports+self.p.exports:
            if self.p.full(e['index'])==path:return e['index']
        raise KeyError(path)
    def name(self,name):
        if name not in self.names:self.names.append(name);self.new_names.append(name)
        return self.names.index(name)
    def call(self,name,*args):return op(0x1b)+ref(self.name(name))+sum(args,Code())+op(0x16)
    def canvas_property(self,name):
        try:return self.obj('Engine.Canvas.'+name)
        except KeyError:pass
        for e in self.new_imports:
            if e['name']==name:return e['index']
        e=dict(index=-len(self.p.imports)-len(self.new_imports)-1, class_package=self.name('Core'),
               class_name=self.name('FloatProperty'),outer=self.obj('Engine.Canvas'),name=name,name_index=self.name(name))
        self.new_imports.append(e);return e['index']
    def link_next(self,index,next_index):
        e=self.p.exports[index-1];b=self.changed.get(index,self.p.raw(e))
        assert b[0]==0
        _,pos=ci(b,1);start=pos;_,end=ci(b,pos)
        self.changed[index]=b[:start]+enc_ci(next_index)+b[end:]
    def add_locals(self,function,last,decls):
        new=[]
        for name,typ in decls:
            idx=len(self.table)+1
            e=dict(index=idx,cls=self.obj('Core.'+typ+'Property'),super=0,outer=function,name=name,
                   name_index=self.name(name),flags=self.p.exports[last-1]['flags'],offset=0,size=0)
            self.table.append(e);self.new_exports.append(e);new.append(idx)
        self.link_next(last,new[0])
        for idx,nextidx in zip(new,new[1:]+[0]):
            self.changed[idx]=b'\0\0'+enc_ci(nextidx)+struct.pack('<II',1,0)+b'\0'
        return [local(i) for i in new]
    def patch(self,path,fn,code,description):
        self.changed[fn.exp['index']]=fn.serialize(code)
        self.notes.append(dict(path=path,index=fn.exp['index'],old_offset=fn.exp['offset'],
                               old_size=fn.exp['size'],new_size=len(self.changed[fn.exp['index']]),description=description))
    def write(self,path):
        p=self.p;out=bytearray(p.data)
        for idx,b in sorted(self.changed.items()):
            self.table[idx-1]['offset']=len(out);self.table[idx-1]['size']=len(b);out+=b
        if self.new_names:
            no=len(out);out+=p.data[p.name_offset:p.name_end]
            for name in self.new_names:out+=enc_ci(len(name)+1)+name.encode('ascii')+b'\0'+struct.pack('<I',0x70010)
            struct.pack_into('<ii',out,12,len(self.names),no)
        if self.new_imports:
            io=len(out);out+=p.data[p.import_offset:p.imports[-1]['end']]
            for e in self.new_imports:
                out+=enc_ci(e['class_package'])+enc_ci(e['class_name'])+struct.pack('<i',e['outer'])+enc_ci(e['name_index'])
            struct.pack_into('<ii',out,28,len(p.imports)+len(self.new_imports),io)
        eo=len(out)
        for e in self.table:
            out+=enc_ci(e['cls'])+enc_ci(e['super'])+struct.pack('<i',e['outer'])+enc_ci(e['name_index'])+struct.pack('<I',e['flags'])+enc_ci(e['size'])
            if e['size']:out+=enc_ci(e['offset'])
        struct.pack_into('<ii',out,20,len(self.table),eo)
        # One generation is serialized in the stock v129 package; update its advertised counts.
        assert struct.unpack_from('<i',out,52)[0]==1
        struct.pack_into('<ii',out,56,len(self.table),len(self.names))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(out)
        blobs=path.parent/(path.stem+'-exports');blobs.mkdir(exist_ok=True)
        for idx,b in self.changed.items():(blobs/(str(idx)+'.bin')).write_bytes(b)
        return dict(input=str(p.path.resolve()),output=str(path.resolve()),old_sha256=hashlib.sha256(p.data).hexdigest(),
                    new_sha256=hashlib.sha256(out).hexdigest(),functions=self.notes,new_names=self.new_names,
                    new_imports=self.new_imports,new_exports=self.new_exports,changed_exports=sorted(self.changed))

def safe_scope(builder,fn,canvas,last):
    width,org,clip=builder.add_locals(fn.exp['index'],last,[('Width','Int'),('X','Float'),('W','Float')])
    def field(name):return ctx(local(canvas),inst(builder.canvas_property(name)),0)
    sx,sy,ox,cx=map(field,['SizeX','SizeY','OrgX','ClipX'])
    safe=native(249,width,cast(68,native(171,cast(63,sy),floating(4/3))))
    enter=(assign(width,sx)+assign(org,ox)+assign(clip,cx)+assign(sx,safe)+
           assign(ox,native(174,org,native(171,cast(63,native(147,width,sx)),floating(0.5))))+
           assign(cx,native(244,clip,cast(63,sx))))
    leave=assign(sx,width)+assign(ox,org)+assign(cx,clip)
    return enter,leave

def build_kw(path,dest):
    b=Builder(path)
    fn=Function(b.p,'KWHud.PostRender')
    enter,leave=safe_scope(b,fn,817,394)
    # Update fScaleX/Y before the item loop; retain the stock physical update after restoration.
    scales=fn.slice(176,210)
    b.patch('KWHud.PostRender',fn,fn.replaced([(0,0,enter+scales),(176,176,leave)]),
            'Scoped centered 4:3 safe area for HudItems and overlays; restore before cutscene borders and Engine.HUD.PostRender.')
    fn=Function(b.p,'KWCutTextController.DrawText')
    enter,leave=safe_scope(b,fn,225,225)
    b.patch('KWCutTextController.DrawText',fn,fn.replaced([(0,0,enter),(544,544,leave)]),
            'Subtitle wrapping/centering and fast-forward icon use the same safe area; exact Canvas metrics restored.')
    return b.write(dest)

def build_sh(path,dest):
    b=Builder(path)
    fn=Function(b.p,'SHHud.DrawLevelAction')
    c=local(140)
    sx=cast(63,ctx(c,inst(b.obj('Engine.Canvas.SizeX'))))
    sy=cast(63,ctx(c,inst(b.obj('Engine.Canvas.SizeY'))))
    badge_x=native(175,native(171,sx,floating(0.5)),native(171,sy,floating(128/600)))
    badge_w=native(171,sy,floating(256/600))
    repl=[(a,a+30,badge_x) for a in (176,489,714)]+[(a,a+30,badge_w) for a in (297,566,791)]
    b.patch('SHHud.DrawLevelAction',fn,fn.replaced(repl),
            'Loading/saving badges retain 256:64 aspect at the screen center; physical black background untouched.')
    fn=Function(b.p,'SHCutTextController.Hourglass.RenderHud','Hourglass.RenderHud.json')
    # Stock SH override uses pixel height as a fraction. Use the sane base-class full-cover states.
    cut=b.obj('KWGame.KWCutTextController.bCutSceneInProgress')
    curr=b.obj('KWGame.KWCutTextController.fCurrBorderHeight')
    body=assign(inst(curr),floating(1.0))
    cond=op(0x2d)+inst(cut)
    tail=assign(inst(curr),floating(0.5))
    height=body+raw(b'\x07'+struct.pack('<H',body.m+3+cond.m+tail.m))+cond+tail
    getx=next(t for t in fn.tokens if t['type']=='VirtualFunctionToken' and t['Position']==78)
    gety=b.call('GetScaleY',local(b.obj('SHCutTextController.Hourglass.RenderHud.Canvas')))
    b.patch('SHCutTextController.Hourglass.RenderHud',fn,fn.replaced([(0,29,height),(78,89,gety)]),
            'Uniform hourglass icon scale; normalized full-screen border height in cutscene and non-cutscene states.')
    # A slot-machine coin originates in physical world space, outside the scoped HUD draw.
    path='SlotMachine.SlotMachineTakeCoins.CoinWorldLocationFromScreen'
    fn=Function(b.p,path,'SlotMachineTakeCoins.CoinWorldLocationFromScreen.json')
    oldx=fn.slice(11,28);physicalw=fn.slice(72,126);physicalh=fn.slice(126,180)
    safe=native(244,physicalw,native(171,physicalh,floating(4/3)))
    mapped=native(174,native(171,native(175,physicalw,safe),floating(0.5)),native(172,native(171,oldx,safe),physicalw))
    b.patch(path,fn,fn.replaced([(11,28,mapped)]),
            'Convert the slot-machine coin source from legacy screen x to the centered HUD safe area before physical world unprojection.')
    return b.write(dest)

def main():
    a=argparse.ArgumentParser();a.add_argument('--kw',type=Path,default=WORK/'audit/gameplay-fix/KWGame.u')
    a.add_argument('--sh',type=Path,default=WORK/'built/System/SHGame.u');a.add_argument('--out',type=Path,default=HERE/'built')
    args=a.parse_args()
    report={'KWGame':build_kw(args.kw,args.out/'KWGame.u'),'SHGame':build_sh(args.sh,args.out/'SHGame.u')}
    (HERE/'metadata.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:{x:v[x] for x in ('output','old_sha256','new_sha256','changed_exports')} for k,v in report.items()},indent=2))

if __name__=='__main__':main()

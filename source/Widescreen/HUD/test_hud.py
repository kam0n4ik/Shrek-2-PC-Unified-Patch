"""Execute the actual rebuilt HUD bytecode against a recording Canvas.

Renderer calls are mocked; this verifies branch paths, dimensions and exact restoration,
not graphics-driver behavior or font rasterization.
"""
from pathlib import Path
import importlib.util, json, math, shutil, struct, sys

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
sys.path.insert(0,str(WORK))
from uepkg import Package
spec=importlib.util.spec_from_file_location('video_vm',WORK/'video-analysis/verify_patch.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def approx(a,b):assert math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-4),(a,b)
def metrics(c):return tuple(c[x] for x in ('SizeX','SizeY','OrgX','ClipX'))

class HudVM(base.VM):
 def __init__(self):
  super().__init__();self.draws=[];self.positions=[];self.snapshots=[];self.unprojected=[]
 def expr(self,n,obj,loc,fn,lvalue=False):
  t=n['type'];c=n['children'];ev=lambda i:self.expr(c[i],obj,loc,fn)
  if t=='NoObjectToken':return None
  if t=='ObjectConstToken':return {'__object__':base.P.full(fn.ref(n))}
  if t=='SkipToken':return ev(0)
  if t=='StructMemberToken':
   r=base.Ref(base.val(ev(0)),base.P.obj(fn.ref(n)));return r if lvalue else r.get()
  if t=='PrimitiveCastToken':
   a=base.val(ev(0));co=n['CastOpCode']
   if co in (58,68):return int(a)
  if t=='NativeFunctionToken':
   sp=n['StoragePosition'];b=fn.raw[sp]
   prefix=c[0]['Position']-n['Position']
   num=((fn.raw[sp-1]-0x60)<<8)|b if prefix==2 else b
   if num in (130,132):
    a=base.truth(self.expr(c[0],self.frames[-1],loc,fn))
    return (a and base.truth(self.expr(c[1],self.frames[-1],loc,fn))) if num==130 else (a or base.truth(self.expr(c[1],self.frames[-1],loc,fn)))
   numeric={145:lambda a,b:int(a/b),146:lambda a,b:a+b,147:lambda a,b:a-b,
            154:lambda a,b:a==b,155:lambda a,b:a!=b,
            171:lambda a,b:a*b,172:lambda a,b:a/b,173:lambda a,b:math.fmod(a,b),
            174:lambda a,b:a+b,175:lambda a,b:a-b,176:lambda a,b:a<b,
            177:lambda a,b:a>b,178:lambda a,b:a<=b,179:lambda a,b:a>=b,
            244:min}
   if num in numeric:
    args=[base.val(self.expr(ch,self.frames[-1],loc,fn)) for ch in c if ch['type']!='EndFunctionParmsToken']
    return numeric[num](*args)
   if num==466:
    args=[base.val(self.expr(ch,self.frames[-1],loc,fn)) for ch in c if ch['type']!='EndFunctionParmsToken']
    self.draws.append((obj.copy(),args));return None
   if num==547:return obj['map']
  return super().expr(n,obj,loc,fn,lvalue)
 def method(self,obj,name,args):
  if name in ('CalculateScaleX','CalculateScaleY'):
   return args[0]['SizeX' if name.endswith('X') else 'SizeY']/obj['fBaseResX' if name.endswith('X') else 'fBaseResY']
  if name in ('GetScaleX','GetScaleY'):
   return obj['fScaleX' if name.endswith('X') else 'fScaleY']
  if name=='RenderHud':
   self.snapshots.append((obj['role'],metrics(args[0]),obj['hud'].get('fScaleX'),obj['hud'].get('fScaleY')))
   return None
  if name in ('Render','PostRender'):
   self.snapshots.append((obj.get('role',name),metrics(args[0]),None,None));return None
  if name=='DrawWrappedText':
   self.snapshots.append(('text',metrics(obj),None,None));return None
  if name=='GetMaxBorderHeight':return 0.125
  if name=='SetPos':obj['CurX'],obj['CurY']=args;self.positions.append((obj.copy(),args));return None
  if name=='SetDrawColor':return None
  if name=='DrawIcon':self.draws.append((obj.copy(),args));return None
  if name=='DynamicLoadObject':return {'USize':64,'VSize':32}
  if name=='DrawBorder':
   self.snapshots.append(('border',metrics(args[0]),obj['fCurrBorderHeight'],obj['bCutSceneInProgress']));return None
  if name in ('UseLargeFont','PrintActionMessage'):return None
  if name=='GetCanvasSizeX':return obj['physical_width']
  if name=='GetCanvasSizeY':return obj['physical_height']
  if name=='GetItemXPos':return int(738*obj['hud']['physical_width']/1024)
  if name=='GetItemYPos':return int(16*obj['hud']['physical_height']/768)
  if name=='KWGetWorldLoc':
   self.unprojected.append(args);return args[0].copy()
  return super().method(obj,name,args)

def load(package, funcs):
 base.P=Package(package);base.TD=HERE/'verified-tokens'
 for full,stem in funcs:
  if full!=stem:shutil.copyfile(base.TD/(stem+'.json'),base.TD/(full+'.json'))
 base.FNS={full:base.Fn(full) for full,stem in funcs}
 return base.P

RES=[(640,480),(800,600),(1024,768),(1280,720),(1366,768),(1600,900),(1920,1080),(2048,1152),(2560,1440)]

def canvas(w,h,org=0,clip=None):
 return dict(SizeX=w,SizeY=h,OrgX=org,ClipX=w if clip is None else clip,CurX=0,CurY=0)

def preservation_tests():
 report=json.loads((HERE/'metadata.json').read_text())
 result={}
 for name,meta in report.items():
  before=Package(meta['input']);after=Package(meta['output']);changed=set(meta['changed_exports'])
  assert before.names==after.names[:len(before.names)]
  for i,e in enumerate(before.imports):
   assert {k:e[k] for k in ('index','class_package','class_name','outer','name')}=={k:after.imports[i][k] for k in ('index','class_package','class_name','outer','name')}
  unchanged=0
  for e,new in zip(before.exports,after.exports):
   for key in ('index','cls','super','outer','name','flags'):assert e[key]==new[key]
   if e['index'] not in changed:
    assert before.raw(e)==after.raw(new),(name,before.full(e['index']))
    unchanged+=1
  # UFunction's Children chain follows NextField through every parameter/local.
  if name=='KWGame':
   from uepkg import ci
   for fn_name,last,expected in [('KWHud.PostRender',817,['C','i','Width','X','W']),('KWCutTextController.DrawText',225,['Canvas','Width','X','W'])]:
    chain=[];idx=last
    while idx:
     assert idx not in [x[0] for x in chain]
     e=after.exports[idx-1];chain.append((idx,e['name']))
     assert after.full(e['outer'])==fn_name
     raw=after.raw(e);_,pos=ci(raw,1);idx,_=ci(raw,pos)
    assert [x[1] for x in chain]==expected,(fn_name,chain)
  result[name]=dict(unchanged_original_exports=unchanged,original_object_indices_preserved=True,original_import_indices_preserved=True)
 return result

def kw_tests():
 p=load(HERE/'built/KWGame.u',[(x,x) for x in ('KWHud.PostRender','KWCutTextController.DrawText')])
 count=0
 for w,h in RES:
  for hidden in (False,True):
   for cut in (False,True):
    for org,clip in ((0,w),(13.25,w-17.5)):
     vm=HudVM();c=canvas(w,h,org,clip);before=metrics(c)
     hud=dict(bHideHUD=hidden,fScaleX=-1,fScaleY=-1,fBaseResX=1024,fBaseResY=768)
     cc=dict(role='cut',hud=hud,bCutSceneInProgress=cut)
     hud['CutTextController']=cc
     hud['HudItems']=[dict(role='item0',hud=hud,bHideDuringCutscene=False),dict(role='item1',hud=hud,bHideDuringCutscene=True)]
     hud['OverlayPages']=[dict(role='overlay')]
     vm.run('KWHud.PostRender',hud,{'C':c,'i':0})
     assert metrics(c)==before,('restore',w,h,hidden,cut,metrics(c),before)
     safe=min(w,int(h*struct.unpack('<f',struct.pack('<f',4/3))[0]));offset=(w-safe)/2
     expected=(safe,h,org+offset,min(clip,safe))
     roles=[]
     for role,m,sx,sy in vm.snapshots:
      roles.append(role)
      assert m==(before if role in ('cut','PostRender') else expected),(role,m,expected,before)
      if role.startswith('item'):
       approx(sx,safe/1024);approx(sy,h/768);approx(sx,sy)
     assert ('item0' in roles)==(not hidden)
     assert ('item1' in roles)==(not hidden and not cut)
     assert ('cut' in roles)==(not hidden)
     assert 'overlay' in roles and 'PostRender' in roles
     approx(hud['fScaleX'],w/1024);approx(hud['fScaleY'],h/768)
     count+=1
  for comment in ('','comment'):
   for ff in (False,True):
    for textures in ([None,None,None],[{'USize':64,'VSize':32}]*3):
     vm=HudVM();c=canvas(w,h,2.5,w-1);before=metrics(c)
     cc=dict(strText='Subtitle',strCutCommentText=comment,fCurrBorderHeight=0.125,colorCutText={},fontTiny={},fontSmall={},fontMed={},bShowFF=ff,textureFFIcons=textures.copy(),curFFIcon=0)
     vm.run('KWCutTextController.DrawText',cc,{'Canvas':c})
     assert metrics(c)==before
     texts=[s for s in vm.snapshots if s[0]=='text']
     assert len(texts)==(2 if comment else 1)
     for _,m,_,_ in texts:
      assert m[0]==min(w,int(h*struct.unpack('<f',struct.pack('<f',4/3))[0]))
      approx(m[2],2.5+(w-m[0])/2)
     assert len(vm.draws)==int(ff)
     count+=1
 # UProperty chain is serialized and owns all new locals; no duplicate existing indexes.
 for name,expected in [('KWHud.PostRender',['C','i','Width','X','W']),('KWCutTextController.DrawText',['Canvas','Width','X','W'])]:
  fn=next(e for e in p.exports if p.full(e['index'])==name)
  children=[e['name'] for e in p.exports if e['outer']==fn['index']]
  assert sorted(children)==sorted(expected),(name,children)
 return count

def sh_tests():
 load(HERE/'built/SHGame.u',[
  ('SHHud.DrawLevelAction','SHHud.DrawLevelAction'),
  ('SHCutTextController.Hourglass.RenderHud','Hourglass.RenderHud'),
  ('SlotMachine.SlotMachineTakeCoins.CoinWorldLocationFromScreen','SlotMachineTakeCoins.CoinWorldLocationFromScreen')])
 count=0
 for w,h in RES:
  for action,mapname in ((0,'normal'),(1,'normal'),(1,'SH2_Preamble.unr'),(2,'normal'),(3,'normal'),(4,'normal')):
   vm=HudVM();c=canvas(w,h);before=metrics(c)
   hud=dict(Level=dict(LevelAction=action,Pauser=None,TimeSeconds=0,PauseDelay=0,PlayerHeroActor=dict(map=mapname)),
            PausedMessage='',ConnectingMessage='Connecting',PrecachingMessage='Precaching',
            Loadimage='loading',saveimage='saving',loadimagesolid='loading-solid',blackimage='black')
   vm.run('SHHud.DrawLevelAction',hud,{'C':c,'BigMessage':''})
   assert metrics(c)==before
   if action in (1,2):
    badges=[(cc,a) for cc,a in vm.draws if a[0]!='black'];assert len(badges)==1
    cc,a=badges[0];approx(a[1]/a[2],4);approx(cc['CurX']+a[1]/2,w/2)
    approx(a[2],h*64/600);approx(cc['CurY'],h*268/600)
    black=[a for cc,a in vm.draws if a[0]=='black']
    assert len(black)==int(mapname=='SH2_Preamble.unr')
    if black:assert black[0][1:3]==[w,h]
   count+=1
  for cut in (False,True):
   vm=HudVM();c=canvas(w,h);before=metrics(c)
   cc=dict(fCurrBorderHeight=0,bCutSceneInProgress=cut,texturewait=[{'USize':128,'VSize':64}],HourglassFrame=0,
           parentHUD=dict(fScaleX=w/1024,fScaleY=h/768))
   vm.run('SHCutTextController.Hourglass.RenderHud',cc,{'Canvas':c,'X':0,'Y':0})
   assert metrics(c)==before
   assert cc['fCurrBorderHeight']==(0.5 if cut else 1)
   assert vm.snapshots[0][1]==before
   d,a=vm.draws[0];approx(a[1]/a[2],2);approx(d['CurX']+a[1]/2,w/2);approx(d['CurY']+a[2]/2,h/2)
   count+=1
  vm=HudVM();hud=dict(physical_width=w,physical_height=h)
  obj=dict(RealHudCoin=dict(hud=hud),Level=dict(PlayerHeroActor=dict(Controller=dict(myHUD=hud))))
  loc=dict(ScreenLocation=dict(X=0,Y=0,Z=0),WorldLoc=dict(X=0,Y=0,Z=0),vLook=dict(X=0,Y=0,Z=0))
  vm.run('SlotMachine.SlotMachineTakeCoins.CoinWorldLocationFromScreen',obj,loc)
  a=vm.unprojected[0];safe=min(w,h*4/3);approx(a[0]['X'],(w-safe)/2+int(738*w/1024)*safe/w)
  assert a[1:3]==[float(w),float(h)]
  assert a[0]['Y']==int(16*h/768)
  count+=1
 return count

if __name__=='__main__':
 report=dict(result='passed',kw_scenarios=kw_tests(),sh_scenarios=sh_tests(),preservation=preservation_tests(),
             checks=['Actual patched bytecode executed','All branch targets and context skip sizes valid',
                     'HUD clipping, safe area, uniform scale, hidden/cutscene paths',
                     'Exact Canvas restoration before physical fullscreen rendering',
                     'Subtitle/FF optional branches','Loading/saving badge aspect and full black cover',
                     'Hourglass cover states and aspect','Slot-machine physical unprojection anchor'])
 (HERE/'test-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

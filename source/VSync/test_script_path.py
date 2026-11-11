"""Read-only regression test of the installed v1.2 VSync bytecode.

Uses actual function tokens/bytes. Engine operations and delegate delivery are mocked;
does not reproduce native heap corruption or prove renderer correctness.
"""
from pathlib import Path
import importlib.util,hashlib,itertools,json,sys

HERE=Path(__file__).resolve().parent;WORK=HERE.parent
sys.path.insert(0,str(WORK))
from uepkg import Package,ci
spec=importlib.util.spec_from_file_location('video_vm',WORK/'video-analysis/verify_patch.py')
vm=importlib.util.module_from_spec(spec);spec.loader.exec_module(vm)
INSTALLED=Path('E:/Shrek 2/System/SHGame.u')
vm.P=Package(INSTALLED);vm.TD=HERE/'installed-tokens'
vm.FNS={p.stem:vm.Fn(p.stem) for p in vm.TD.glob('*.json')}

class TraceVM(vm.VM):
 def __init__(self,*args,dispatch=True,resize_callback=False,**kwargs):
  super().__init__(*args,**kwargs);self.dispatch=dispatch;self.resize_callback=resize_callback
  self.trace=[];self.maxdepth=0
 def run(self,name,obj,loc=None):
  self.trace.append({'function':name,'depth':len(self.frames)})
  self.maxdepth=max(self.maxdepth,len(self.frames)+1)
  return super().run(name,obj,loc)
 def console(self,s):
  result=super().console(s)
  if s.lower().startswith('setres ') and self.resize_callback:
   # Adversarial synchronous refresh: model callbacks occurring within SetRes.
   self.run('Tab_OptionsVideo.Refresh',self.video)
  return result
 def method(self,obj,name,args):
  result=super().method(obj,name,args)
  if name=='SetText' and self.dispatch and obj in [self.video['cbResolution'],self.video['cbColorDepth'],self.video['cbRenderer']]:
   # GUIEditBox.SetText always invokes OnChange; ComboBox.TextChanged forwards self.
   self.run('Tab_OptionsVideo.TabOptions_OnChange',self.video,{'Sender':obj})
  return result

def native_commands(v):return [s for s in v.commands if s.lower().startswith(('set ','setres '))]
def setres_commands(v):return [s for s in v.commands if s.lower().startswith('setres ')]

def behavioral_tests():
 counts=dict(selection_only=0,apply_confirmation=0,empty_execute=0)
 samples=[]
 for mode,oldvs,newvs,initialized in itertools.product([False,True],repeat=4):
  v=TraceVM(mode,oldvs,res='1920x1080');v.controller['bCurMenuInitialized']=initialized
  v.video['cbRenderer']['text']='On' if newvs else 'Off'
  v.run('Tab_OptionsVideo.TabOptions_OnChange',v.video,{'Sender':v.video['cbRenderer']})
  assert native_commands(v)==[],v.commands
  assert v.video['btnApplyVideoChangesVisible']==initialized
  counts['selection_only']+=1
 for oldmode,newmode,oldvs,newvs,same_res,callback in itertools.product([False,True],repeat=6):
  for outcome in ('accept','decline','timeout'):
   v=TraceVM(oldmode,oldvs,res='1920x1080',resize_callback=callback)
   v.video['cbRenderer']['text']='On' if newvs else 'Off'
   v.video['cbColorDepth']['text']='Full' if newmode else 'Window'
   desired='1920x1080' if same_res else '2560x1440'
   v.video['cbResolution']['Edit']['text']=desired
   assert v.run('Tab_OptionsVideo.ApplyChanges',v.video,{'Sender':v.video['btnApplyVideoChanges']}) is True
   commands=native_commands(v)
   expected=[f'set ini:Engine.Engine.RenderDevice UseVSync {newvs}',
             'set ini:Engine.Engine.RenderDevice Use16bit False',
             'set ini:Engine.Engine.RenderDevice MaxResWidth 2560',
             'set ini:Engine.Engine.RenderDevice MaxResHeight 1440',
             'setres '+desired+'x32'+('f' if newmode else 'w')]
   assert commands==expected,(commands,expected)
   assert v.dialog['originalbitdepth']==str(oldvs).lower()
   assert v.dialog['OrigRes']=='1920x1080x32'+('f' if oldmode else 'w')
   assert (v.vsync,v.fullscreen,v.res)==(newvs,newmode,desired)
   assert v.startup==oldmode
   if outcome=='timeout':
    v.dialog['Count']=1;v.run('VideoChangeOK.Timer',v.dialog)
   else:
    v.run('VideoChangeOK.InternalOnClick',v.dialog,{'Sender':v.dialog['btnAccept'] if outcome=='accept' else v.dialog['btnDecline']})
   expectedmode=newmode if outcome=='accept' else oldmode
   assert (v.vsync,v.fullscreen,v.res,v.startup)==(
    newvs if outcome=='accept' else oldvs,expectedmode,desired if outcome=='accept' else '1920x1080',expectedmode)
   assert len(setres_commands(v))==(1 if outcome=='accept' else 2)
   # Forwarded SetText callbacks and the synthetic native resize callback never re-enter Execute.
   assert sum(t['function']=='VideoChangeOK.Execute' for t in v.trace)==1
   assert v.maxdepth<10,v.maxdepth
   if oldmode and oldvs and not newvs and same_res and not callback and outcome=='accept':
    samples.append({'outcome':outcome,'commands':v.commands,'calls':v.trace})
   counts['apply_confirmation']+=1
 for mode,vs in itertools.product([False,True],repeat=2):
  v=TraceVM(mode,vs);v.run('VideoChangeOK.Execute',v.dialog,{'DesiredRes':''})
  assert v.commands==[];counts['empty_execute']+=1
 return counts,samples

def binding_checks():
 original=Package(WORK/'original/System/SHGame.u')
 current=vm.P;result={}
 # Exact binding instructions survive patching, rather than relying only on decompiled text.
 for source,pkg in [('original',original),('installed',current)]:
  meta=json.loads((HERE/(source+'-tokens')/'Tab_OptionsVideo.InitComponent.json').read_text())
  e=next(e for e in pkg.exports if pkg.full(e['index'])=='Tab_OptionsVideo.InitComponent')
  code=pkg.raw(e)[meta['offset']:meta['offset']+meta['size']]
  bindings=[]
  for i,t in enumerate(meta['tokens']):
   if t['type']!='LetDelegateToken' or t['Position']<100:continue
   rhs=next(x for x in meta['tokens'][i+1:] if x['type']=='DelegatePropertyToken')
   lhs=next(x for x in reversed(meta['tokens'][i+1:meta['tokens'].index(rhs)]) if x['type']=='InstanceVariableToken')
   prop=ci(code,lhs['StoragePosition']+1)[0];name=ci(code,rhs['StoragePosition']+1)[0]
   bindings.append({'offset':t['Position'],'property_ref':prop,'property':pkg.full(prop),
                    'target_name_index':name,'target_name':pkg.names[name],
                    'bytes':code[t['StoragePosition']:t['StoragePosition']+t['StorageSize']].hex()})
  result[source]=bindings
 assert [x['bytes'] for x in result['original']]==[x['bytes'] for x in result['installed']]
 assert result['installed'][0]['property']=='GUI.GUIComponent.__OnChange__Delegate'
 assert result['installed'][0]['target_name']=='TabOptions_OnChange'
 assert result['installed'][0]['property_ref']==-702
 assert result['installed'][0]['target_name_index']==1302
 assert result['installed'][1]['target_name']=='None'
 # Prove all application/confirmation functions in the installed 1.2 match the reviewed build.
 build=Package(WORK/'built/System/SHGame.u');comparisons=[]
 for name in ('VideoChangeOK.Execute','VideoChangeOK.InternalOnClick','VideoChangeOK.Timer',
              'VideoChangeOK.startTimer','Tab_OptionsVideo.ApplyChanges','Tab_OptionsVideo.TabOptions_OnChange',
              'Tab_OptionsVideo.TabOptions_OnLoadINI','Tab_OptionsVideo.Refresh'):
  a=next(e for e in current.exports if current.full(e['index'])==name)
  b=next(e for e in build.exports if build.full(e['index'])==name)
  assert current.raw(a)==build.raw(b),(name,a,b)
  comparisons.append({'function':name,'index':a['index'],'offset':a['offset'],'size':a['size'],
                      'sha256':hashlib.sha256(current.raw(a)).hexdigest()})
 result['unchanged_reviewed_functions']=comparisons
 return result

if __name__=='__main__':
 bindings=binding_checks();counts,samples=behavioral_tests()
 report={'result':'passed','installed_sha256':hashlib.sha256(vm.P.data).hexdigest(),
         'counts':counts,'branch_context_validation':'all dumped installed functions passed',
         'delegate_binding_checks':bindings,'same_res_off_sample':samples,
         'limits':'Native ConsoleCommand/rendering and delegate storage are mocked. These tests found no script control-flow defect; they do not exclude heap corruption or native crashes.'}
 (HERE/'test-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({k:report[k] for k in ('result','installed_sha256','counts','branch_context_validation','limits')},indent=2))

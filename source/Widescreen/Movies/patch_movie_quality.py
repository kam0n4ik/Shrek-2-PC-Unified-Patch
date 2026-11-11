"""Postprocess HUD-built packages to select the highest supplied movie variant.

Never overwrites either input. Actual current viewport width comes from WinDrv
GETCURRENTRES; stale fullscreen settings cannot influence windowed selection.
"""
from pathlib import Path
import argparse,json,subprocess,sys,hashlib,re

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
sys.path.insert(0,str(WORK/'widescreen'/'hud'))
from build_hud import Builder,Function,raw

DUMPER=WORK/'tools'/'ue-explorer'/'ue-explorer'/'DumpTokens.exe'
INSPECT=WORK/'tools'/'ue-explorer'/'ue-explorer'/'Inspect.exe'
OLD='get ini:Engine.Engine.ViewportManager FullscreenViewportX'
NEW='GETCURRENTRES'

def dump(path,dest,function):
    dest.mkdir(parents=True,exist_ok=True)
    run=subprocess.run([str(DUMPER),str(path),str(dest),function],capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stdout+run.stderr)
    token=dest/(function+'.json')
    assert token.exists(),(function,run.stdout)
    return token

def patch(path,dest,function,label):
    assert path.resolve()!=dest.resolve(),'Input package must not be overwritten'
    before=dump(path,HERE/('quality-tokens-before-'+label),function)
    b=Builder(path)
    fn=Function(b.p,function,str(before))
    queries=[t for t in fn.tokens if t['type']=='StringConstToken' and t.get('Value')==OLD]
    assert len(queries)==3,[(t['type'],t.get('Value')) for t in fn.tokens if t['type']=='StringConstToken']
    const=next(t for t in fn.tokens if t['type']=='IntConstToken' and t.get('Value')==1024)
    conditional=next(t for t in fn.tokens if t['type']=='NativeFunctionToken' and t['Position']+1==const['Position'])
    sp=fn.bound[conditional['Position']]
    assert fn.code[sp]==154,'Expected native EqualEqual_IntInt, with 1024 on the left'
    changes=[(t['Position'],t['Position']+t['Size'],raw(b'\x1f'+NEW.encode()+b'\0')) for t in queries]
    changes.append((conditional['Position'],conditional['Position']+1,raw(bytes([152]))))
    b.patch(function,fn,fn.replaced(changes),
            'Use the actual GETCURRENTRES viewport width; use the supplied 1024 movie variant when active width >=1024.')
    report=b.write(dest)
    after=dump(dest,HERE/('quality-tokens-after-'+label),function)
    afn=Function(b.p,function,str(before)) # source metadata is only used for preservation checks
    from uepkg import Package
    actual=Package(dest)
    newfn=Function(actual,function,str(after))
    assert not any(t.get('Value')==OLD for t in newfn.tokens)
    newqueries=[t for t in newfn.tokens if t['type']=='StringConstToken' and t.get('Value')==NEW]
    assert len(newqueries)==3
    conditions=[]
    for query in newqueries:
        parent=max((t for t in newfn.tokens if t['type']=='NativeFunctionToken' and
                    t['Position']<query['Position']<t['Position']+t['Size']),key=lambda t:t['Position'])
        operand=next(t for t in newfn.tokens if t['Position']==parent['Position']+1)
        assert operand['type']=='IntConstToken'
        native=newfn.code[newfn.bound[parent['Position']]]
        conditions.append((native,operand['Value'],query['Value']))
    assert conditions==[(154,512,NEW),(154,640,NEW),(152,1024,NEW)],conditions
    # All unmodified serialized exports must stay byte-for-byte equal even when
    # input already contains HUD/video/gameplay fixes and added object tables.
    for exp in b.p.exports:
        if exp['index']!=fn.exp['index']:
            assert b.p.raw(exp)==actual.raw(actual.exports[exp['index']-1]),b.p.full(exp['index'])
    cases=[]
    for width,height in [(512,384),(640,480),(800,600),(1024,768),(1280,720),(1366,768),
                         (1600,900),(1920,1080),(2048,1152),(2560,1440)]:
        for fullscreen,saved_full_width in [(True,width),(False,512),(False,1920),(False,640)]:
            reply=f'{width}x{height}'
            def console(command):
                assert command==NEW
                return reply
            selected='default'
            for (opcode,left,command),variant in zip(conditions,['512','640','1024']):
                # UE's int(string) uses the leading decimal integer, appAtoi.
                right=int(re.match(r'\d+',console(command)).group(0))
                matched=(left==right) if opcode==154 else (left<=right)
                if matched:selected=variant;break
            expected='512' if width==512 else '640' if width==640 else '1024' if width>=1024 else 'default'
            assert selected==expected,(function,width,fullscreen,saved_full_width,selected)
            cases.append({'active_width':width,'active_height':height,'fullscreen':fullscreen,
                          'saved_fullscreen_width':saved_full_width,'selected_variant':selected})
    decompiled=HERE/('quality-source-'+label)
    run=subprocess.run([str(INSPECT),str(dest),str(decompiled),function.split('.')[0]],capture_output=True,text=True)
    if run.returncode:raise RuntimeError(run.stdout+run.stderr)
    report['conditions_from_redecoded_bytecode']=conditions
    report['selection_cases']=cases
    report['source']=str(decompiled/(function.split('.')[0]+'.uc'))
    report['unchanged_exports_verified']=len(b.p.exports)-1
    report['runtime_game_verified']=False
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sh',type=Path,required=True)
    ap.add_argument('--kw',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    report={'SHGame':patch(args.sh,args.out/'SHGame.u','SHMovieManager.Trigger','sh'),
            'KWGame':patch(args.kw,args.out/'KWGame.u','ResolutionBasedMovieTrigger.Activate','kw')}
    (HERE/'movie-quality-evidence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{x:v[x] for x in ['input','output','old_sha256','new_sha256','changed_exports','unchanged_exports_verified']} for k,v in report.items()},indent=2))

if __name__=='__main__':main()

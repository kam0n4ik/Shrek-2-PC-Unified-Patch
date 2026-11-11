from pathlib import Path
import json,gzip,hashlib,base64,struct,shutil
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'outputs'/'Shrek2VideoPatch'
OUT.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(b):return base64.b64encode(b).decode('ascii')
def differing_ranges(original,patched):
    common=min(len(original),len(patched))
    ranges=[];start=None;last=None
    for i in range(common):
        if original[i]!=patched[i]:
            if start is None:start=i
            elif i-last>16:ranges.append((start,last+1));start=i
            last=i
    if start is not None:ranges.append((start,last+1))
    if len(original)!=len(patched):ranges.append((common,len(original)))
    return ranges

files=[]
final=ROOT/'widescreen/final/System'
for name in ['SHGame.u','Engine.dll','HpMenu.int','WinDrv.dll','KWGame.u','GUI.dll','D3DDrv.dll']:
    original=(ROOT/'original/System'/name).read_bytes()
    patched=(final/name).read_bytes()
    ranges=differing_ranges(original,patched)
    hunks=[]
    for a,b in ranges:
        after=patched[a:] if a==min(len(original),len(patched)) and len(original)!=len(patched) else patched[a:b]
        hunks.append({'Offset':a,'Before':enc(original[a:b]),'After':enc(after)})
    prior={'SHGame.u':['96e3ba2ad800d2b57a3a49b69cadbc2597dca47f75c4a69861863e452d5861bd',
                       '872fe63f115524b682373d340569870ec851e0091796c656c0509fdf9b24b4f3'],
           'KWGame.u':['58aea9b412f044c4ee30daff975822fe192866f73e4f6cb6f8c06674e9800b89'],
           'D3DDrv.dll':['fb879caf403b7dc4779da228edb54f746d4104ea333b39ac226a280e3b96023c']}
    files.append({'Name':name,'OriginalHash':sha(original),'PatchedHash':sha(patched),
                  'PriorPatchedHashes':prior.get(name,[]),'Hunks':hunks})
manifest={'Version':'1.3','Files':files}
(ROOT/'patch.json.gz').write_bytes(gzip.compress(json.dumps(manifest,separators=(',',':')).encode('utf-8'),mtime=0))
print(json.dumps([{k:v for k,v in f.items() if k!='Hunks'} for f in files],indent=2))

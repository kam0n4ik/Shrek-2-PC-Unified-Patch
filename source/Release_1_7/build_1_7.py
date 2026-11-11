"""Shrek2VideoPatch 1.7 = 1.6 + two developer bug fixes.

1. Maps\\7_Prison_Donkey.unr: the top ladder point AutoLadder513 of the first ladder (LadderVolume0) sits at
   Z=306.5. KWHeroController.PlayerClimbing only dismounts at the top when
   Pawn.Location.Z + CollisionHeight >= TopOfLadder.Location.Z, and that height is only reachable by
   overshooting with large frame steps, so at high FPS Puss can't get off the ladder (softlock).
   Every deleted AutoLadder left in this map from earlier builds of the same ladder has its top at Z=258.5,
   so Location.Z and ColLocation.Z go back to 258.500031 (-48). This matches the community fix by Master_64.
2. SHGame.u, ShHeroPawn.UseShrinkPotion: both calls to ShrinkCameraSetting (which does
   KWHeroController(Controller).Camera without a check) now go to the developers' own guarded
   AdjustShrinkCameraSetting. It has the same body plus Controller/Camera None checks and an early return
   when the camera is already set. AI-controlled companions no longer log "Accessed None" every frame
   while they shrink or grow (663 warnings in one Castle Siege session).
"""
from pathlib import Path
import base64, gzip, hashlib, json, struct, subprocess, sys, zlib

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
GAME = Path('E:/Shrek 2')
sys.path.insert(0, str(WORK))
from uepkg import Package, enc_ci

R15 = WORK / 'release_1_5'
OLD = ['SHGame.u', 'Engine.dll', 'HpMenu.int', 'WinDrv.dll', 'KWGame.u', 'GUI.dll', 'D3DDrv.dll', 'Cutscenes\\GAMEMENU.int']
MAP = '..\\Maps\\7_Prison_Donkey.unr'
NAMES = OLD + [MAP]
LADDER_OFFSETS = [186143 + 8, 186158 + 8]
OLD_Z = struct.pack('<f', 306.500031)
NEW_Z = struct.pack('<f', 258.500031)


def sha(b): return hashlib.sha256(b).hexdigest()
def enc(b): return base64.b64encode(b).decode('ascii')
def rel(n): return n[3:] if n.startswith('..\\') else 'System\\' + n


def embedded_manifest(exe):
    d = exe.read_bytes(); i = 0
    while True:
        i = d.find(b'\x1f\x8b\x08', i)
        if i < 0: raise ValueError(exe)
        try: return json.loads(zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(d[i:]))
        except Exception: i += 1


def ranges(original, patched):
    common = min(len(original), len(patched)); out = []; start = last = None
    for i in range(common):
        if original[i] != patched[i]:
            if start is None: start = i
            elif i - last > 16: out.append((start, last + 1)); start = i
            last = i
    if start is not None: out.append((start, last + 1))
    if len(original) != len(patched): out.append((common, len(original)))
    return out


orig, final = {}, {}
for n in OLD:
    orig[n] = (R15 / 'original/System' / n).read_bytes()
    final[n] = (R15 / 'final/System' / n).read_bytes()

m16 = embedded_manifest(WORK / 'release_1_6/Shrek2VideoPatch-1.6.exe')
v16 = {f['Name']: f for f in m16['Files']}
for n in OLD:
    assert sha(orig[n]) == v16[n]['OriginalHash'] and sha(final[n]) == v16[n]['PatchedHash'], n

# 1. ladder
mp = (GAME / 'Maps/7_Prison_Donkey.unr').read_bytes()
saved_map = GAME / 'System/Shrek2VideoPatchBackup/Maps/7_Prison_Donkey.unr'
if saved_map.exists(): mp = saved_map.read_bytes()
for o in LADDER_OFFSETS: assert mp[o:o + 4] == OLD_Z, (o, mp[o:o + 4].hex())
p = Package(GAME / 'Maps/7_Prison_Donkey.unr')
e = next(e for e in p.exports if e['name'] == 'AutoLadder513')
assert e['offset'] <= LADDER_OFFSETS[0] and LADDER_OFFSETS[1] + 4 <= e['offset'] + e['size']
orig[MAP] = mp
m = bytearray(mp)
for o in LADDER_OFFSETS: m[o:o + 4] = NEW_Z
final[MAP] = bytes(m)

# 2. shrink camera
p = Package(R15 / 'final/System/SHGame.u')
nm = {n: i for i, n in enumerate(p.names)}
old_call = b'\x1b' + enc_ci(nm['ShrinkCameraSetting'])
new_call = b'\x1b' + enc_ci(nm['AdjustShrinkCameraSetting'])
assert len(old_call) == len(new_call) == 3
e = next(e for e in p.exports if p.full(e['index']) == 'ShHeroPawn.UseShrinkPotion')
body = p.raw(e)
pos = [i for i in range(len(body)) if body.startswith(old_call, i)]
assert pos == [149, 312], pos
sh = bytearray(final['SHGame.u'])
for i in pos:
    a = e['offset'] + i
    assert sh[a:a + 3] == old_call
    sh[a:a + 3] = new_call
diff = [i for i in range(len(sh)) if sh[i] != final['SHGame.u'][i]]
assert len(diff) == 4, diff
final['SHGame.u'] = bytes(sh)

for n in NAMES:
    d = HERE / 'final' / rel(n); d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(final[n])
    d = HERE / 'original' / rel(n); d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(orig[n])

prior = {n: set() for n in NAMES}
for f in m16['Files']:
    prior[f['Name']].add(f['PatchedHash']); prior[f['Name']].update(f.get('PriorPatchedHashes') or [])

files = []
for n in NAMES:
    o, t = orig[n], final[n]
    hunks = []
    for a, b in ranges(o, t):
        after = t[a:] if a == min(len(o), len(t)) and len(o) != len(t) else t[a:b]
        hunks.append({'Offset': a, 'Before': enc(o[a:b]), 'After': enc(after)})
    files.append({'Name': n, 'OriginalHash': sha(o), 'PatchedHash': sha(t),
                  'PriorPatchedHashes': sorted(prior[n] - {sha(t), sha(o)}), 'Hunks': hunks})

(HERE / 'patch.json.gz').write_bytes(gzip.compress(json.dumps({'Version': '1.7', 'Files': files}, separators=(',', ':')).encode('utf-8'), mtime=0))
exe = HERE / 'Shrek2VideoPatch-1.7.exe'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe', '/nologo', '/target:winexe', '/out:' + str(exe),
                '/resource:' + str(HERE / 'patch.json.gz') + ',patch.json.gz',
                '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll', str(HERE / 'PatchInstaller.cs')], check=True)
print(json.dumps({'exe_sha256': sha(exe.read_bytes()),
                  'files': [{'Name': f['Name'], 'Orig': f['OriginalHash'][:12], 'Patched': f['PatchedHash'][:12], 'prior': len(f['PriorPatchedHashes']), 'hunks': len(f['Hunks'])} for f in files]}, indent=1))

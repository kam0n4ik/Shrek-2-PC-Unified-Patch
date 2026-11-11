"""Shrek2VideoPatch 1.5 = 1.4 + intro skip.

1. SHGame.u, SHMovieManager.Trigger: `WhichMovie == MovieList.Length` -> `WhichMovie < MovieList.Length`
   (native 154 -> 150, one byte). The first trigger at SH2_Preamble start takes the existing
   end-of-logos branch: LoadLevel(NextLevel = Book_FrontEnd.unr). Logos are never started.
2. Cutscenes\\GAMEMENU.int: camera snaps to the final menu view (FlyTo without Time = instant),
   book open / page turn animations play at Rate=2.0 instead of 0.5. Same cues, same GotoMenu.
"""
from pathlib import Path
import base64, gzip, hashlib, json, shutil, subprocess, sys, zlib

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
GAME = Path('E:/Shrek 2/System')
sys.path.insert(0, str(WORK))
from uepkg import Package

SHGAME_14 = '7f86eca8a87444a778bc9df812dcb9392479a7c57ddeb9788a590e2f4ca643ec'
GAMEMENU_ORIG = '7bc4ddfc6115023369a54c20c8b69ed02fc6f8f95a5d6a5d2924f71104573af0'
COND_OLD = bytes.fromhex('07 3e 01 9a 01 51 11 37 01 69 2c 16')
COND_NEW = bytes.fromhex('07 3e 01 96 01 51 11 37 01 69 2c 16')
NAMES = ['SHGame.u', 'Engine.dll', 'HpMenu.int', 'WinDrv.dll', 'KWGame.u', 'GUI.dll', 'D3DDrv.dll', 'Cutscenes\\GAMEMENU.int']

GAMEMENU_FAST = '''[CutScene]
line_0=NoBypass
[Sequence_0]
PawnTag=MAIN
line_0=FadeTo Time=0
line_1=PlayMusic temp_storybook_intro_music Fade=0.0 Loop=True
line_2=Trigger LightMover1
line_3=FadeIn Time=1
line_4=Cue _CAMERA_0
line_5=Cue _SHMENUBOOK_1
line_6=Cue _SHREK_2
line_7=Cue _SHMENUBOOK_3
[Sequence_1]
PawnTag=CAMERA
line_0=WaitForCue _CAMERA_0
line_1=TargetFlyTo Menu_Target3
line_2=FlyTo Menu_Cam3
line_3=Cue ReadyToOpenBook
line_4=Cue 1ndPageTurn
line_5=WaitForCue CutEnd
[Sequence_2]
PawnTag=SHMENUBOOK
line_0=WaitForCue _SHMENUBOOK_1
line_1=WaitForCue ReadyToOpenBook
line_2=PlaySound Page_Turn
line_3=PlayAnim BookOpen Rate=2.0
line_4=WaitForAnim
line_5=PlayAnim OpenedStatic Loop
line_6=WaitForCue 1ndPageTurn
line_7=PlaySound Page_Turn2
line_8=PlayAnim Page1Turn Rate=2.0
line_9=WaitForAnim
line_10=PlayAnim Page1turnedStatic Loop
line_11=GotoMenu SHGame.ShFEGUIPage
line_12=WaitForCue _SHMENUBOOK_3
line_13=WaitForCue CutEnd
[Sequence_3]
PawnTag=SHREK
line_0=WaitForCue _SHREK_2
line_1=WaitForCue CutEnd
'''.replace('\n', '\r\n').encode('ascii')


def sha(b): return hashlib.sha256(b).hexdigest()
def enc(b): return base64.b64encode(b).decode('ascii')


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


final = HERE / 'final/System'
orig_dir = HERE / 'original/System'
for d in (final / 'Cutscenes', orig_dir / 'Cutscenes'): d.mkdir(parents=True, exist_ok=True)

for n in NAMES[:-1]:
    b = (GAME / 'Shrek2VideoPatchBackup' / n).read_bytes()
    assert b == (WORK / 'original/System' / n).read_bytes(), n
    (orig_dir / n).write_bytes(b)
gm_src = GAME / 'Cutscenes/GAMEMENU.int'
gm_saved = GAME / 'Shrek2VideoPatchBackup/Cutscenes/GAMEMENU.int'
gm = (gm_saved if gm_saved.exists() else gm_src).read_bytes()
assert sha(gm) == GAMEMENU_ORIG
(orig_dir / 'Cutscenes/GAMEMENU.int').write_bytes(gm)

m14 = embedded_manifest(WORK / 'release_1_4/Shrek2VideoPatch-1.4.exe')
v14 = {f['Name']: f['PatchedHash'] for f in m14['Files']}
for n in NAMES[:-1]:
    b = (GAME / n).read_bytes()
    if n == 'SHGame.u' and sha(b) != SHGAME_14:
        b = (WORK / 'vsync/v14/built/System/SHGame.u').read_bytes()
    assert sha(b) == v14[n], n
    (final / n).write_bytes(b)

sh = bytearray((final / 'SHGame.u').read_bytes())
p = Package(final / 'SHGame.u')
e = next(e for e in p.exports if p.full(e['index']) == 'SHMovieManager.Trigger')
body = p.raw(e); assert body.count(COND_OLD) == 1
off = e['offset'] + body.index(COND_OLD)
sh[off:off + len(COND_OLD)] = COND_NEW
(final / 'SHGame.u').write_bytes(bytes(sh))
q = Package(final / 'SHGame.u')
assert [x for x in p.exports] == [x for x in q.exports]
diff = [i for i in range(len(sh)) if sh[i] != p.data[i]]
assert diff == [off + 3], diff
(final / 'Cutscenes/GAMEMENU.int').write_bytes(GAMEMENU_FAST)

prior = {n: set() for n in NAMES}
for v in ['1.1', '1.2', '1.3']:
    for f in embedded_manifest(WORK / f'Shrek2VideoPatch-{v}.exe')['Files']:
        prior[f['Name']].add(f['PatchedHash']); prior[f['Name']].update(f.get('PriorPatchedHashes') or [])
for f in m14['Files']:
    prior[f['Name']].add(f['PatchedHash']); prior[f['Name']].update(f.get('PriorPatchedHashes') or [])

files = []
for n in NAMES:
    o = (orig_dir / n).read_bytes(); t = (final / n).read_bytes()
    hunks = []
    for a, b in ranges(o, t):
        after = t[a:] if a == min(len(o), len(t)) and len(o) != len(t) else t[a:b]
        hunks.append({'Offset': a, 'Before': enc(o[a:b]), 'After': enc(after)})
    files.append({'Name': n, 'OriginalHash': sha(o), 'PatchedHash': sha(t),
                  'PriorPatchedHashes': sorted(prior[n] - {sha(t), sha(o)}), 'Hunks': hunks})

(HERE / 'patch.json.gz').write_bytes(gzip.compress(json.dumps({'Version': '1.5', 'Files': files}, separators=(',', ':')).encode('utf-8'), mtime=0))
exe = HERE / 'Shrek2VideoPatch-1.5.exe'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe', '/nologo', '/target:winexe', '/out:' + str(exe),
                '/resource:' + str(HERE / 'patch.json.gz') + ',patch.json.gz',
                '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll', str(HERE / 'PatchInstaller.cs')], check=True)
print(json.dumps({'exe_sha256': sha(exe.read_bytes()), 'shgame_trigger_patch_offset': off + 3,
                  'files': [{'Name': f['Name'], 'PatchedHash': f['PatchedHash'][:16], 'prior': len(f['PriorPatchedHashes']), 'hunks': len(f['Hunks'])} for f in files]}, indent=1))

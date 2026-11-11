"""Shrek2VideoPatch 1.4: 1.3 + SHGame.u bool-bytecode fix (VSync crash) + WinDrv.dll Alt+F4 -> WM_CLOSE.

Originals: game backup folder (verified against work/original). Patched: files verified live in E:\\Shrek 2\\System.
Prior patched hashes: every PatchedHash from installers 1.1-1.3 so upgrade and restore accept them.
"""
from pathlib import Path
import base64, gzip, hashlib, json, shutil, subprocess, zlib

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
GAME = Path('E:/Shrek 2/System')
NAMES = ['SHGame.u', 'Engine.dll', 'HpMenu.int', 'WinDrv.dll', 'KWGame.u', 'GUI.dll', 'D3DDrv.dll']
EXPECTED = {
    'SHGame.u': '7f86eca8a87444a778bc9df812dcb9392479a7c57ddeb9788a590e2f4ca643ec',
    'WinDrv.dll': '6af2fc5f2f995fbf0f34028da880bf56dda0539c4a13617627d666e883b804af',
}


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


prior = {n: set() for n in NAMES}
for v in ['1.1', '1.2', '1.3']:
    for f in embedded_manifest(WORK / f'Shrek2VideoPatch-{v}.exe')['Files']:
        prior[f['Name']].add(f['PatchedHash']); prior[f['Name']].update(f.get('PriorPatchedHashes') or [])

files = []
for name in NAMES:
    original = (GAME / 'Shrek2VideoPatchBackup' / name).read_bytes()
    assert original == (WORK / 'original/System' / name).read_bytes(), name
    patched = (GAME / name).read_bytes()
    if name in EXPECTED: assert sha(patched) == EXPECTED[name], name
    else: assert patched == (WORK / 'widescreen/final/System' / name).read_bytes(), name
    hunks = []
    for a, b in ranges(original, patched):
        after = patched[a:] if a == min(len(original), len(patched)) and len(original) != len(patched) else patched[a:b]
        hunks.append({'Offset': a, 'Before': enc(original[a:b]), 'After': enc(after)})
    files.append({'Name': name, 'OriginalHash': sha(original), 'PatchedHash': sha(patched),
                  'PriorPatchedHashes': sorted(prior[name] - {sha(patched), sha(original)}), 'Hunks': hunks})

manifest = {'Version': '1.4', 'Files': files}
(HERE / 'patch.json.gz').write_bytes(gzip.compress(json.dumps(manifest, separators=(',', ':')).encode('utf-8'), mtime=0))
shutil.copy2(WORK / 'PatchInstaller.cs', HERE / 'PatchInstaller.cs')
exe = HERE / 'Shrek2VideoPatch-1.4.exe'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe', '/nologo', '/target:winexe', '/out:' + str(exe),
                '/resource:' + str(HERE / 'patch.json.gz') + ',patch.json.gz',
                '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll', str(HERE / 'PatchInstaller.cs')], check=True)
print(json.dumps({'exe_sha256': sha(exe.read_bytes()),
                  'files': [{k: f[k] for k in ('Name', 'OriginalHash', 'PatchedHash', 'PriorPatchedHashes')} | {'hunks': len(f['Hunks'])} for f in files]}, indent=1))

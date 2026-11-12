"""Shrek2VideoPatch 1.8 = 1.7 + Options -> Controls tab.

1. System\\S2Controls.u (new file): class S2Controls.Tab_OptionsControls, compiled from
   source/S2Controls/Classes/Tab_OptionsControls.uc with UCC from UE2 Runtime (build 2226,
   community setup github.com/Master-64/Shrek2-LevelEditor). 24 actions on 4 pages, up to two keys each.
2. SHGame.u, Tab_Options.AddTabs: one statement appended before the final return:
       tabOptions.AddTab("YZPABLEHNE", "S2Controls.Tab_OptionsControls",, "HACTPONKN YZPABLEHNR",
                         false, Class'GUI.SHGUITabButton3Options');
   GUITabControl.AddTab loads the panel class by name (DynamicLoadObject). The function has no jumps,
   so nothing else moves. The new export body and a new export table are appended (same scheme as 1.3).
"""
from pathlib import Path
import base64, gzip, hashlib, json, struct, subprocess, sys, zlib

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(WORK))
from uepkg import Package, enc_ci

R17 = WORK / 'release_1_7'
OLD = ['SHGame.u', 'Engine.dll', 'HpMenu.int', 'WinDrv.dll', 'KWGame.u', 'GUI.dll', 'D3DDrv.dll',
       'Cutscenes\\GAMEMENU.int', '..\\Maps\\7_Prison_Donkey.unr']
NEW = 'S2Controls.u'
TAB_CAPTION = 'YZPABLEHNE'            # УПРАВЛЕНИЕ in the game's Russian font encoding
TAB_HINT = 'HACTPONKN YZPABLEHNR'     # НАСТРОЙКИ УПРАВЛЕНИЯ
TAB_CLASS = 'S2Controls.Tab_OptionsControls'


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
    orig[n] = (R17 / 'original' / rel(n)).read_bytes()
    final[n] = (R17 / 'final' / rel(n)).read_bytes()

m17 = embedded_manifest(R17 / 'Shrek2VideoPatch-1.7.exe')
v17 = {f['Name']: f for f in m17['Files']}
for n in OLD:
    assert sha(orig[n]) == v17[n]['OriginalHash'] and sha(final[n]) == v17[n]['PatchedHash'], n

# --- SHGame.u: Tab_Options.AddTabs gets a fourth AddTab call ---------------------------------
p = Package(R17 / 'final/System/SHGame.u')
data = bytearray(p.data)


def idx(path):
    for e in p.imports + p.exports:
        if p.full(e['index']) == path: return e['index']
    raise KeyError(path)


TABOPT = idx('Tab_Options.tabOptions')
BTN3 = idx('GUI.SHGUITabButton3Options')
BVISIBLE = idx('GUI.GUIComponent.bVisible')
ADDTAB = p.names.index('AddTab')

def ref(n): return (enc_ci(n), 4)
def s(t): b = b'\x1f' + t.encode('ascii') + b'\0'; return (b, len(b))
def cat(*parts): return (b''.join(x[0] for x in parts), sum(x[1] for x in parts))
def op(b): return (bytes([b]), 1)

call = cat(op(0x1b), ref(ADDTAB), s(TAB_CAPTION), s(TAB_CLASS), op(0x0b), s(TAB_HINT), op(0x28),
           op(0x20), ref(BTN3), op(0x16))
stmt = cat(op(0x19), op(0x01), ref(TABOPT), (struct.pack('<HB', call[1], 4), 3), call)

table = [dict(e) for e in p.exports]
moved = {}
# Main menu (Tab_Options) and pause menu (Tab_InGameOptions overrides AddTabs) both get the fourth tab.
for fn, mem_expected in (('Tab_Options.AddTabs', 205), ('Tab_InGameOptions.AddTabs', 211)):
    exp = next(e for e in p.exports if p.full(e['index']) == fn)
    body = p.raw(exp)
    # The three original statements use the same context, function name and (for Sound) button class.
    assert body.count(b'\x19\x01' + enc_ci(TABOPT)) == 3 and body.count(b'\x1b' + enc_ci(ADDTAB)) == 3, fn
    assert body.count(b'\x20' + enc_ci(BTN3)) == 1, fn
    script_start = body.index(b'\x0f\x01')
    mem_size, = struct.unpack_from('<i', body, script_start - 4)
    assert mem_size == mem_expected, (fn, mem_size)
    ret = body.rindex(b'\x16\x04\x0b') + 1          # final "return;" (04 0b)
    assert ret > script_start
    new_body = bytearray(body[:ret] + stmt[0] + body[ret:])
    struct.pack_into('<i', new_body, script_start - 4, mem_size + stmt[1])
    table[exp['index'] - 1]['offset'] = len(data); table[exp['index'] - 1]['size'] = len(new_body)
    data += new_body
    moved[exp['index']] = bytes(new_body)

# Pause menu video tab: Internal_OnDraw forced lblRenderer/cbRenderer/lblObjectDetail/cbObjectDetail
# invisible every frame. In this patch the renderer slot is the VSync switch, so VSync (and object detail)
# vanished from the pause menu. The hidden branch "Controls[i].bVisible = false" becomes "= true",
# same length, so the pause menu shows the same controls as the main menu.
exp = next(e for e in p.exports if p.full(e['index']) == 'Tab_InGameOptionsVideo.Internal_OnDraw')
body = p.raw(exp)
hide = b'\x2d\x01' + enc_ci(BVISIBLE) + b'\x28'
assert body.count(hide) == 1, body.count(hide)
k = exp['offset'] + body.index(hide) + len(hide) - 1
assert data[k] == 0x28
data[k] = 0x27
table_offset = len(data)
for e in table:
    data += enc_ci(e['cls']) + enc_ci(e['super']) + struct.pack('<i', e['outer']) + enc_ci(e['name_index']) + struct.pack('<I', e['flags']) + enc_ci(e['size'])
    if e['size']: data += enc_ci(e['offset'])
struct.pack_into('<i', data, 24, table_offset)
final['SHGame.u'] = bytes(data)

tmp = HERE / '_check_SHGame.u'; tmp.write_bytes(final['SHGame.u'])
q = Package(tmp); tmp.unlink()
assert len(q.exports) == len(p.exports) and q.names == p.names
changed = []
for a, b in zip(p.exports, q.exports):
    if a['index'] in moved: assert q.raw(b) == moved[a['index']]
    elif p.raw(a) != q.raw(b): changed.append(p.full(a['index']))
assert changed == ['Tab_InGameOptionsVideo.Internal_OnDraw'], changed

# --- S2Controls.u (new file) -----------------------------------------------------------------
pkg = (HERE / 'source' / NEW).read_bytes()
sp = Package(HERE / 'source' / NEW)
assert [sp.full(e['index']) for e in sp.exports if e['outer'] == 0] == ['Tab_OptionsControls']

for n in OLD:
    d = HERE / 'final' / rel(n); d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(final[n])
    d = HERE / 'original' / rel(n); d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(orig[n])
(HERE / 'final/System' / NEW).write_bytes(pkg)

prior = {n: set() for n in OLD + [NEW]}
# First 1.8 build (installed on 11-12 13:05, never published): only main-menu tab, SaveConfig in the panel.
m18a = embedded_manifest(HERE / 'Shrek2VideoPatch-1.8-first.exe')
for f in m17['Files'] + m18a['Files']:
    prior[f['Name']].add(f['PatchedHash']); prior[f['Name']].update(f.get('PriorPatchedHashes') or [])

files = []
for n in OLD:
    o, t = orig[n], final[n]
    hunks = []
    for a, b in ranges(o, t):
        after = t[a:] if a == min(len(o), len(t)) and len(o) != len(t) else t[a:b]
        hunks.append({'Offset': a, 'Before': enc(o[a:b]), 'After': enc(after)})
    files.append({'Name': n, 'OriginalHash': sha(o), 'PatchedHash': sha(t),
                  'PriorPatchedHashes': sorted(prior[n] - {sha(t), sha(o)}), 'Hunks': hunks})
files.append({'Name': NEW, 'Added': True, 'OriginalHash': '', 'PatchedHash': sha(pkg), 'PriorPatchedHashes': sorted(prior[NEW] - {sha(pkg)}),
              'Hunks': [{'Offset': 0, 'Before': '', 'After': enc(pkg)}]})

(HERE / 'patch.json.gz').write_bytes(gzip.compress(json.dumps({'Version': '1.8', 'Files': files}, separators=(',', ':')).encode('utf-8'), mtime=0))
exe = HERE / 'Shrek2VideoPatch-1.8.exe'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe', '/nologo', '/target:winexe', '/out:' + str(exe),
                '/resource:' + str(HERE / 'patch.json.gz') + ',patch.json.gz',
                '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll', str(HERE / 'PatchInstaller.cs')], check=True)
print(json.dumps({'exe_sha256': sha(exe.read_bytes()), 'addtabs_added_bytes': len(stmt[0]), 'addtabs_mem_added': stmt[1],
                  'files': [{'Name': f['Name'], 'Orig': f['OriginalHash'][:12], 'Patched': f['PatchedHash'][:12], 'prior': len(f['PriorPatchedHashes']), 'hunks': len(f['Hunks'])} for f in files]}, indent=1))

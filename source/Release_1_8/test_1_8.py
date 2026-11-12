"""Installer 1.8 scenarios on copies of game files (never touches E:\\Shrek 2 or the real User.ini)."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, zlib

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = Path('E:/shrek2-tests/1.8')
EXE18 = HERE / 'Shrek2VideoPatch-1.8.exe'
EXE17 = WORK / 'release_1_7/Shrek2VideoPatch-1.7.exe'
FAKE_PROFILE = ROOT / 'no-such-profile/User.ini'


def sha(b): return hashlib.sha256(b).hexdigest()


def manifest(exe):
    d = exe.read_bytes(); i = 0
    while True:
        i = d.find(b'\x1f\x8b\x08', i)
        try: return json.loads(zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(d[i:]))
        except Exception: i += 1


M = manifest(EXE18)
files = M['Files']


def path(game, name): return game / 'System' / name


def fresh(name):
    game = ROOT / name
    if game.exists(): shutil.rmtree(game)
    for f in files:
        if f.get('Added'): continue
        rel = f['Name'][3:] if f['Name'].startswith('..\\') else 'System\\' + f['Name']
        dst = game / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / 'original' / rel, dst)
    return game


def run(exe, game, *args):
    rep = game / 'report.txt'
    rc = subprocess.run([str(exe), '--system', str(game / 'System'), '--profile', str(FAKE_PROFILE), '--report', str(rep), *args]).returncode
    return rc, rep.read_text(encoding='utf-8-sig') if rep.exists() else ''


def state(game):
    out = {}
    for f in files:
        p = path(game, f['Name'])
        out[f['Name']] = sha(p.read_bytes()) if p.exists() else None
    return out


def is_final(game): return all(state(game)[f['Name']] == f['PatchedHash'] for f in files)
def is_orig(game):
    s = state(game)
    return all((s[f['Name']] is None) if f.get('Added') else s[f['Name']] == f['OriginalHash'] for f in files)


results = {}
# A: clean install -> restore
g = fresh('A'); rc1, r1 = run(EXE18, g); a1 = is_final(g)
backup_ok = (g / 'System/Shrek2VideoPatchBackup/Maps/7_Prison_Donkey.unr').exists() and not (g / 'System/Shrek2VideoPatchBackup/S2Controls.u').exists()
rc2, r2 = run(EXE18, g, '--restore'); a2 = is_orig(g)
results['A_clean_install_restore'] = rc1 == 0 and a1 and backup_ok and rc2 == 0 and a2
# B: 1.7 installed -> 1.8 upgrade -> restore
g = fresh('B'); rc0, _ = run(EXE17, g); rc1, r1 = run(EXE18, g); b1 = is_final(g)
rc2, _ = run(EXE18, g, '--restore')
results['B_upgrade_from_1_7_restore'] = rc0 == 0 and rc1 == 0 and b1 and rc2 == 0 and is_orig(g)
# C: double install is idempotent
g = fresh('C'); run(EXE18, g); s1 = state(g); rc, _ = run(EXE18, g)
results['C_reinstall_idempotent'] = rc == 0 and state(g) == s1 and is_final(g)
# D: foreign S2Controls.u blocks install, nothing changed
g = fresh('D'); path(g, 'S2Controls.u').write_bytes(b'not ours'); before = state(g)
rc, r = run(EXE18, g)
results['D_foreign_file_refused'] = rc == 1 and state(g) == before and 'S2Controls.u' in r
# E: --check leaves files untouched
g = fresh('E'); before = state(g); rc, r = run(EXE18, g, '--check')
results['E_check_only'] = rc == 0 and state(g) == before and not (g / 'System/Shrek2VideoPatchBackup').exists()
# F: restore after 1.8 when S2Controls.u was already removed by hand
g = fresh('F'); run(EXE18, g); path(g, 'S2Controls.u').unlink(); rc, _ = run(EXE18, g, '--restore')
results['F_restore_without_new_file'] = rc == 0 and is_orig(g)
# G: the 1.7 installer doesn't know the 1.8 SHGame.u: it must refuse to restore and change nothing
g = fresh('G'); run(EXE18, g); s1 = state(g); rc, r = run(EXE17, g, '--restore')
results['G_old_installer_refuses_safely'] = rc == 1 and state(g) == s1 and 'SHGame.u' in r

# H: first 1.8 build (installed live on 11-12) -> current 1.8 -> restore
EXE18A = HERE / 'Shrek2VideoPatch-1.8-first.exe'
g = fresh('H'); rc0, _ = run(EXE18A, g); rc1, r1 = run(EXE18, g); h1 = is_final(g)
rc2, _ = run(EXE18, g, '--restore')
results['H_upgrade_from_first_1_8_restore'] = rc0 == 0 and rc1 == 0 and h1 and rc2 == 0 and is_orig(g)

print(json.dumps(results, indent=1))
sys.exit(0 if all(results.values()) else 1)

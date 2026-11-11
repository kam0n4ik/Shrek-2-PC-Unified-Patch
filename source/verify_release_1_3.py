"""Exercise the actual compiled installer on scratch copies of all seven files."""
from pathlib import Path
import gzip, hashlib, json, shutil, subprocess

WORK = Path(__file__).resolve().parent
EXE = WORK / 'Shrek2VideoPatch-1.3.exe'
TEST = WORK / 'release-1.3-tests'
SYSTEM = TEST / 'System'
SYSTEM.mkdir(parents=True, exist_ok=True)
MANIFEST = json.loads(gzip.decompress((WORK / 'patch.json.gz').read_bytes()))
FILES = MANIFEST['Files']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = []

def install(label, *args, expected=0):
    report = TEST / (label + '.txt')
    result = subprocess.run([str(EXE), '--system', str(SYSTEM), '--report', str(report), *args])
    assert result.returncode == expected, (label, result.returncode, report.read_text(encoding='utf-8-sig'))
    checks.append(label)

def verify(key):
    for f in FILES:
        assert sha(SYSTEM / f['Name']) == f[key], f['Name']

for f in FILES:
    shutil.copy2(WORK / 'original/System' / f['Name'], SYSTEM / f['Name'])
install('fresh-check', '--check')
install('fresh-install')
verify('PatchedHash')
install('repeat-install')
verify('PatchedHash')
install('restore', '--restore')
verify('OriginalHash')

for f in FILES:
    shutil.copy2(WORK / 'widescreen/final/System' / f['Name'], SYSTEM / f['Name'])
shutil.copy2(WORK / 'widescreen/movies/D3DDrv.previous-1.2.dll', SYSTEM / 'D3DDrv.dll')
install('upgrade-1.2-check', '--check')
install('upgrade-1.2')
verify('PatchedHash')
install('upgraded-repeat')
verify('PatchedHash')
install('upgraded-restore', '--restore')
verify('OriginalHash')

changed = bytearray((SYSTEM / 'GUI.dll').read_bytes())
changed[0] ^= 1
(SYSTEM / 'GUI.dll').write_bytes(changed)
before = {f['Name']: sha(SYSTEM / f['Name']) for f in FILES}
install('unsupported-input-rejected', expected=1)
assert before == {f['Name']: sha(SYSTEM / f['Name']) for f in FILES}
checks.append('rejected-input-changes-nothing')

evidence = {'version': MANIFEST['Version'], 'status': 'passed', 'checks': checks,
            'files': len(FILES), 'all_original_backups_preserved': True}
for f in FILES:
    assert sha(SYSTEM / 'Shrek2VideoPatchBackup' / f['Name']) == f['OriginalHash']
(TEST / 'installer-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps(evidence, indent=2))

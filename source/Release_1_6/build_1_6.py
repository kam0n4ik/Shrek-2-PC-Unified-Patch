"""Shrek2VideoPatch 1.6 = game files of 1.5 + optional dev-menu key unlock in the installer (F9/F10 in User.ini)."""
from pathlib import Path
import gzip, hashlib, json, subprocess

HERE = Path(__file__).resolve().parent
m = json.loads(gzip.decompress((HERE.parent / 'release_1_5/patch.json.gz').read_bytes()))
assert m['Version'] == '1.5'
m['Version'] = '1.6'
(HERE / 'patch.json.gz').write_bytes(gzip.compress(json.dumps(m, separators=(',', ':')).encode('utf-8'), mtime=0))
exe = HERE / 'Shrek2VideoPatch-1.6.exe'
subprocess.run([r'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe', '/nologo', '/target:winexe', '/out:' + str(exe),
                '/resource:' + str(HERE / 'patch.json.gz') + ',patch.json.gz',
                '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll', str(HERE / 'PatchInstaller.cs')], check=True)
print(hashlib.sha256(exe.read_bytes()).hexdigest())

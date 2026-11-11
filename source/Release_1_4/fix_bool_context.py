"""In-place-length correction of the one malformed boolean lvalue; workspace output only."""
from pathlib import Path
import argparse,hashlib,json,sys

HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]
sys.path.insert(0,str(WORK));from uepkg import Package

BAD=bytes.fromhex('14 2d 19 01 6d 05 05 00 04 01 c2 03 27')
GOOD=bytes.fromhex('14 19 01 6d 05 06 00 04 2d 01 c2 03 27')

def main():
 a=argparse.ArgumentParser();a.add_argument('--input',type=Path,default=WORK/'widescreen/final/System/SHGame.u')
 a.add_argument('--output',type=Path,default=HERE/'built/System/SHGame.u');args=a.parse_args()
 p=Package(args.input);e=next(e for e in p.exports if p.full(e['index'])=='Tab_OptionsVideo.TabOptions_OnChange')
 body=p.raw(e);assert body.count(BAD)==1
 off=e['offset']+body.index(BAD)
 out=p.data[:off]+GOOD+p.data[off+len(BAD):]
 assert len(out)==len(p.data) and len(BAD)==len(GOOD)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(out)
 q=Package(args.output)
 for old,new in zip(p.exports,q.exports):
  assert old==new
  if old['index']!=e['index']:assert p.raw(old)==q.raw(new)
 report=dict(input=str(args.input.resolve()),output=str(args.output.resolve()),
             old_sha256=hashlib.sha256(p.data).hexdigest(),new_sha256=hashlib.sha256(out).hexdigest(),
             export_index=e['index'],export_offset=e['offset'],export_size=e['size'],
             patch_file_offset=off,patch_export_offset=off-e['offset'],old_bytes=BAD.hex(' '),new_bytes=GOOD.hex(' '),
             storage_length_unchanged=True,memory_length_unchanged=True,
             changed_file_bytes=[i for i in range(len(out)) if p.data[i]!=out[i]])
 (HERE/'metadata.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

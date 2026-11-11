"""Run the inserted x86 scaler with frames decoded by the shipped Bink DLL.

DecodeContract.cs executes BinkCopyToBuffer natively in a 32-bit process and
checks its buffer contract. Here the scaler itself executes under Unicorn;
only its malloc/free/copy imports are stubbed, using those real decoder bytes.
This is offline integration coverage, not live game playback.
"""
from pathlib import Path
import hashlib, json
from PIL import Image
from verify_movies import run

HERE = Path(__file__).resolve().parent
DATA = HERE / 'decoder-integration'
contract = json.loads((DATA / 'decoder-contract.json').read_text())
assert contract['actual_native_decoder'] and contract['process_bits'] == 32
results = []
cases = [(0, 4, 1280, 720), (0, 4, 2560, 1440),
         (1, 2, 1280, 720), (2, 4, 1920, 1080), (3, 2, 1366, 768)]
for index, bpp, width, height in cases:
    case = contract['cases'][index]
    decoder = case['copy32' if bpp == 4 else 'copy16']
    source = (DATA / decoder['tight_file']).read_bytes()
    assert hashlib.sha256(source).hexdigest() == decoder['tight_sha256']
    for guard in ['guard_before', 'guard_after_logical', 'guard_after_physical', 'row_padding_unchanged']:
        assert decoder[guard]
    result, output, pitch = run(case['width'], case['height'], width, height,
                                bpp=bpp, source=source)
    result.update(movie=case['file'], frame=case['frame'],
                  actual_decoder_flags=decoder['format_flags'],
                  decoder_sha256=contract['decoder_sha256'])
    if bpp == 4:
        picture = Image.frombytes('RGB', (width, height), output, 'raw', 'BGRX', pitch)
        preview = f'decoder-scaler-{Path(case["file"]).stem}-{width}x{height}.png'
        picture.save(HERE / preview)
        result['preview'] = preview
    results.append(result)
    print(json.dumps(result), flush=True)

evidence = {'status': 'passed', 'actual_bink_decoder_cases': len(contract['cases']) * 2,
            'emulated_scaler_with_actual_decoder_frames': results,
            'live_game_playback_verified': False}
(HERE / 'decoder-scaler-evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')

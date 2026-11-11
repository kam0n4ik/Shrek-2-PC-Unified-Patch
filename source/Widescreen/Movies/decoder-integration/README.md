# Actual Bink decoder contract

`DecodeContract.cs` is an independent x86 .NET Framework harness. It calls the stdcall exports of the installed `E:\Shrek 2\System\binkw32.dll` directly; it does not use FFmpeg, mocked pixels, the game process, or a graphics window.

Decoder SHA-256: `e78ef7e8ed68067c0ecd813f6114f5a9e45541411f104496b4cdcfab234d0a0b`.

## Results

Four real BIK frames were decoded in both formats (eight successful native copies): FGMcommercial1024 frame 241, KWLogo1024 frame 37, ACTIVSN512 frame 20, and DW_LOGO640 frame 20.

| Native copy flags | Actual output | Matching D3D format |
| --- | --- | --- |
| `0x80000005` | 4 bytes/pixel, BGRX, X = 0 | `D3DFMT_X8R8G8B8` = 22 (`0x16`) |
| `0x8000000A` | 2 bytes/pixel, little-endian RGB565 | `D3DFMT_R5G6B5` = 23 (`0x17`) |

All eight correct copies preserve the prefix guard, logical-end guard, physical-end guard, and 32-byte row padding. Expanded RGB565 differs from BGRX by at most `[7, 3, 7]` RGB levels in each frame, consistent with 5:6:5 quantization. `decoder-contract.json` contains buffer sizes, pitches, guard results, and hashes; `colour-evidence.json` contains the channel comparisons. The `.raw` buffers and `.png` previews were produced from the actual decoder output.

## Expected-failure negative control

`cases[0].negative_control_old_mapping` intentionally supplies flags `0x80000005` with a 2-byte/pixel logical allocation and pitch 2080 for the 1024x768 FGM frame. A larger 32-bit physical reservation safely contains the expected overwrite. The real decoder corrupts the logical-end guard and row padding, while the prefix and physical-end guards remain intact. This reproduces the original mapping defect without a process-level heap overflow. The `NEGATIVE-*.raw` file is deliberately corrupt and must not be used as a correct frame.

## Reproduce

From the workspace root, compile using `C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe` with `/platform:x86`, `/reference:System.Web.Extensions.dll`, and input `DecodeContract.cs`. Run `DecodeContract.exe` with this directory as its output argument. The harness fails on an unexpected guard result.

This evidence validates the real decoder format contract and buffer bounds. Scaler execution is separately covered by the parent's `decoder-scaler-evidence.json`, which executes the patched x86 code in Unicorn using these native decoder buffers. This harness does not execute the scaler natively or launch the game.

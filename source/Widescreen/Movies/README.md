# Movie aspect-fit patch

`patch_movies.patch_bytes(original_d3ddrv_bytes)` returns the modified D3DDrv.dll. It requires SHA256 `5ff643295ef507e399ccd4c886f9f36928f7ea43d815c58004176aa557706c61`. Corrected version 1.3 result SHA256 is `2524499a9bf51795798e5d037b0cfe8f9d165d1820ac433262c9e39ebd7232d4`.

Only file offsets `0x244A5..0x244A9` and `0x1800..0x19F6` change. The first is a 5-byte jump on two complete original instructions. The second is 503 bytes inside verified executable CC padding. No new absolute address needs relocation: call/pop obtains the actual image base and existing import slots resolve malloc/free/BinkCopyToBuffer. The unused original block, including its existing import relocation, remains intact.

Version 1.2 mistakenly treated D3D format 22 as 16-bit, and reversed the Bink copy flags. Its decoder stub repeated that same assumption, so previous mock tests missed real memory corruption. Version 1.3 matches the original renderer and actual installed decoder: format 22 = X8R8G8B8, 4 Bpp, flags `0x80000005`; format 23 = R5G6B5, 2 Bpp, flags `0x8000000A`. Other formats are rejected safely without allocating or copying. Actual negative-control decoding with the old mapping overwrites the logical-end canary and row padding; all eight corrected native copies preserve both. See `decoder-integration/README.md`.

The stock movie path is:

1. SHMovieManager, ResolutionBasedMovieTrigger or MovieTrigger sets both HUD.MoviePos coordinates to -1 and calls `Movie.Play`.
2. Engine UMovie creates the render-device FMovie implementation. Frame time, movie end and `MovieEnded` callback live in Engine FBinkMovie and stay unchanged.
3. `UD3DRenderDevice.RenderMovie` at VA `0x10014C80` obtains the backbuffer surface and calls its movie's RenderToNative.
4. D3D Bink RenderToNative at `0x100243B0` calls the original Engine FBinkMovie.PreRender, locks the surface, clears it black, and originally copies unscaled decoded pixels into its center. This explains the small 800/1024-pixel movie on a 1440p viewport.
5. The hook after the unchanged black clear decodes into a temporary frame with the same original Bink format flags, computes `scale=min(targetW/sourceW,targetH/sourceH)`, and copies it into the centered destination rectangle. It frees the temporary allocation before returning to the existing unlock/cleanup path.

All 17 BIK headers were inspected. Every supplied frame is 4:3: 512×384, 640×480, 800×600 or 1024×768. At 2560×1440 the destination is 1920×1440 at x=320, so the whole frame is visible with black side bars. No movie files change. Sampling is nearest neighbour. Existing audio, skip commands, callbacks and subtitle code are not changed. This is the D3D renderer path; Pixo and the separate MovieTexture material pipeline retain their existing behavior. Stock script producers all request centering; positive-position custom movie mods were not tested.

Validation:

- `verify_movies.py`: seven complete machine-code tests covering pixel output, row pitch, border blackness, allocation/free order, buffer canaries, register/stack restoration, relocation to another image base, 16-bit output, downscaling, portrait target and malloc failure.
- Twenty-four actual source-size/viewport rectangle cases through the inserted machine code, including 2560×1440.
- `decoder-integration/DecodeContract.cs` executes the actual 32-bit Bink DLL on four real movies in both formats, checks buffer canaries/padding, and safely reproduces the old mapping failure as a negative control. Color agreement between RGB565 and BGRX is within quantization [7,3,7].
- `verify_decoder_scaler.py` runs five frames produced by that native decoder through the corrected inserted x86 code, with full pixel comparisons up to 2560×1440. `decoder-scaler-evidence.json` records exact flags, decoder hash and fit rectangles. These are offline emulations, not screenshots of a running game. The FGM 1280×720 preview was visually inspected.
- The earlier FFmpeg-frame previews cover geometry only and did not exercise the real Bink copy contract; they are not evidence for the corrected decoder integration.
- Live playback in the game has not been verified, following the user's Esc stop of computer input.

`patch_movie_quality.py --sh INPUT_SH --kw INPUT_KW --out NEW_OUTPUT_DIR` is a separate postprocessor to run after the HUD package edits. It changes only SHMovieManager.Trigger and ResolutionBasedMovieTrigger.Activate. All three viewport queries become GETCURRENTRES; 512/640 selection stays exact and the highest supplied 1024 variant is chosen when actual active width is >=1024. It reparses the output functions, checks 40 selection scenarios per package (including stale fullscreen config while windowed), and checks every other export is byte-identical to input. Its outputs are intended to enter the unified installer, not a second user-facing patch.

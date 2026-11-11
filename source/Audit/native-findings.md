# Native compatibility / inherited input review

This is a read-only review of the supplied installed build. It does not claim
exhaustive decompilation or runtime testing of every native procedure. Alt+F4,
camera projection, video-mode caps, and VSync were handled by the primary audit
and are not repeated here.

## Confirmed latent defect: integer weights disable mode-2 release smoothing

**Location:** `Engine.u`, `Engine.PlayerInput.SmoothMouse`, export 5448;
`work/audit/source/Engine/PlayerInput.uc:169`, `:238`, `:239`.

The routine declares `local int i, sum`. In the zero-movement branch for
`MouseSmoothingMode > 1`, its three iterations add
`int(float(i + 1) * 0.1)` to `sum`. The terms are 0, 0, and 0. Consequently
the next expression `aMouse += float(sum) * OldSamples[i]` contributes zero,
even when nonzero prior samples exist, before those samples are cleared.

This is present in the compiled package, not just a type inference by the
decompiler: `PlayerInput.SmoothMouse.sum` is export 1928 with class
`IntProperty`. The token dump includes the explicit float-to-int cast (cast
opcode 68) before the native integer `+=`. Core native definitions independently
identify native 161 as integer `+=`, 171 as float `*`, and 172 as float `/`.
Evidence: `tokens/PlayerInput.SmoothMouse.json`, `input-edge-evidence.json`.

**Trigger and impact:** selecting smoothing mode 2 or higher, then stopping
mouse motion, discards the weighted release tail. `PlayerController` exposes
`SetMouseSmoothing(int Mode)` at source line 982, so the branch can be selected.
Shipping/default `MouseSmoothingMode=1`, so the current default profile does not
activate this particular branch. Shrek's active `ShPlayerInput` inherits this
same `SmoothMouse` routine (`ShPlayerInput.uc:24–25`).

**Fix direction:** use the float weights directly, or a float accumulator,
then verify whether the intended tail is cumulative weights .1/.3/.6 or direct
weights .1/.2/.3. The source does not establish which response was intended.
No gameplay/input behavior was changed automatically in this audit.

**Confidence:** high that integer truncation makes the branch ineffective;
intended smoothing response and player-visible reproduction are unverified.

## Confirmed arithmetic boundary; physical trigger still unverified

**Location:** native `Engine.dll` input command `COUNT`,
VA `0x1042AB91–0x1042ABEC` (file increment at `0x12ABEA`);
`Engine.PlayerController.bXAxis` / `bYAxis` are bytes;
`Engine.PlayerInput.SmoothMouse` at source line 222 divides by `float(SampleCount)`
without first checking for zero.

`COUNT` increments the destination with `inc byte ptr [eax]` at
`0x1042ABEA`, without saturation. Therefore 256 axis records between resets
produce counter zero. The default bindings in `System/DefUser.ini:108–109`
connect MouseX/MouseY to `Count bXAxis` / `Count bYAxis` followed by the movement
axis command. `ShHeroController.InputClass` is `ShPlayerInput`
(`ShHeroController.uc:831`), and that class calls the inherited `SmoothMouse`.

`UWindowsViewport.UpdateInput` drains DirectInput records one at a time from
`0x111062E0` through its `GetDeviceData` call at `0x11106311`; nonempty axis records
are dispatched at `0x11106343` and `0x1110635D`, then it loops. A fixed per-frame
axis-record limit is not present in that loop. The configured DirectInput queue
capacity and a real device reaching 256 records in a frame were not established.

At the arithmetic boundary, `Core.dll`'s actual
`UObject::execDivide_FloatFloat` ends with unguarded x87 `fdiv` at
`0x10136E60`. With the normal masked x87 exceptions, a nonzero value divided
by a wrapped count of zero produces infinity. Five cases of the actual native
increment instruction (1/255/256/257/512 samples) and the real x87 arithmetic
sequence were executed in Unicorn. The results match byte wraparound and
infinite division. This is CPU emulation, not running-game evidence.

**Potential impact:** wrong smoothing normalization after counter wrap; an
exact multiple of 256 can produce nonfinite mouse state. A camera jump or a
crash in the real game is not claimed.

**Fix direction:** an early zero-count fallback in the smoothing function can
prevent nonfinite math; full fidelity for large event counts requires widening
or otherwise accurately representing the sample counter. Saturating the byte
alone avoids zero but still misrepresents the sample count. Validate with real
high-polling-rate input and long frame times before a behavioral patch.

**Confidence:** high for the byte overflow and nonfinite arithmetic; medium/
unverified for physical reachability and player-visible effects on this PC.

## Coverage and exclusions

`module-inventory.json` inventories PE metadata, hashes, exports, and import
module counts for the shipped DLL/EXE files. Focused machine-code inspection
covered the Windows input pump, mouse-record dispatch, generic COUNT command,
float arithmetic, and the corresponding active script inheritance/bindings.
Inherited engine input scripts were reviewed using the fully exported source
tree, with package table/token corroboration for the integer-weight finding.

Neither absence of modern OS features, unused editor/native exports, nor
decompiler `PropertyTag` warnings were counted as application bugs. The review
does not establish that every save/load path, audio driver path, or native
function is correct; those remaining bodies would need further targeted
static/runtime work. No files under the installed game or user profile were
changed by this subtask.

## Follow-up: negative options-tab position at high resolutions

**Location:** `SHGame.Tab_Options.InitComponent`,
`work/audit/source/SHGame/Tab_Options.uc:47–55`.

The initialization reads the *saved fullscreen width* and calculates
`WinLeft = .5 - (.315 * (width / 800)) / 2`. At width 2560 the value is -.004;
in a window it also depends on the unrelated saved fullscreen setting rather
than the active viewport.

Native `GUI.dll UGUIComponent::ActualLeft` (export trampoline `0x1000198D`,
implementation `0x1001AA10`) treats every WinLeft below 1, including negative
values, as a fraction of viewport width or bound-parent width. Negative values
are not a right-edge anchor. `UGUIComponent::UpdateBounds` at `0x10016F90` writes
this result directly into hit-test bounds without clamping. The native
`UGUITabControl::PreDraw` row-placement loop calls `ActualLeft` through its
vtable at `0x1001E827` and adds the result to tab-button placement.

The *actual shipped ActualLeft function* was executed in Unicorn for 18 cases:
512/640/800/1024/1280/1920/2560 widths, two saved-vs-current window mismatch
cases, and both parent-bound and viewport-relative branches. At 2560 the
native result is -10.2400007 pixels for a full-page parent at x=0. Thus the
negative coordinate is confirmed, not merely inferred from a script formula.

**Bounded repair:** feed the formula the current viewport width, capped at the
largest original supported value 1024. This preserves the original results
for active 512/640/800/1024 widths, prevents negative tab positions above 1024,
and removes dependence on a stale fullscreen width while windowed. All 18
native coordinate cases pass with this proposal. It does not establish exact
caption-group centering at new resolutions; that still needs visual QA.

`Tab_OptionsGame.InitComponent` only uses width to select its 512-pixel special
label-width branch, so it does not have the same unbounded high-resolution
coordinate formula. No additional change there is required to fix this issue.

Evidence: `gui-layout-evidence.json`, `verify_gui_layout.py`,
`ActualLeft_UGUIComponent.asm`, `UpdateBounds_UGUIComponent.asm`, and
`PreDraw_UGUITabControl.asm`.

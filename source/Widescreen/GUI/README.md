# GUI widescreen layout patch

Prepared against `GUI.dll` SHA-256
`8a964d576f315ddc6a3bbcf4b86d44c36a7d86ae70a350f7bf78a75f38fe7e08`.
Patched SHA-256:
`971aef9f8018ad2475d7a8cd4494ad59c6d8f7c658fda6f78b8aa9ffdac017b7`.

`patch_gui.py` reads the installed original but writes only this work directory.
`GUI.patched.dll` is ready for isolated game testing and integration in the
single installer. Nothing was installed by this subtask.

## Coordinate path

For wide viewports use `V = min(W, 4H/3)` and `X0 = (W - V)/2`.
The root relative GUI geometry becomes:

```
ActualWidth = WinWidth * V
ActualLeft = X0 + WinLeft * V
```

Parent-scaled width and parent-bound positions keep the original recursion.
They therefore inherit the root 4:3 width and offset exactly once. Height and
top calculations stay unchanged. Unbound absolute pixel positions keep their
original physical-pixel meaning, which avoids offsetting cursor-positioned
generic windows a second time. The shipped SHGame menu scripts inspected use
relative root WinLeft values; nested pixel button positions inherit their owner.

Hooks:

- `UGUIComponent::ActualWidth`, VA `0x1001A7FC`, six bytes replacing the root
  `FILD viewport.SizeX` with a call returning the effective width.
- `UGUIComponent::ActualLeft`, VA `0x1001AABE`, nine bytes replacing the root
  relative multiply with effective width plus centered offset.
- `UGUIFont::execGetFont`, VA `0x10019BCB`, five bytes after Canvas/XRes argument
  parsing. The font selection XRes is capped to `floor(4 * Canvas.SizeY / 3)`.
  `GUIStyles::TextSize` and `GUIStyles::DrawText` both route through this function,
  so measurement and drawing choose fonts from the same height-based reference.

The helper payload is 160 bytes in the original executable CC padding at
VA `0x10003000`. The patch adds no absolute addresses or HIGHLOW relocations.
All overwritten bytes, original hash, CC padding, exports, and actual relocation
entries are checked. PE ABSOLUTE/type-0 relocation padding is ignored correctly.

## Input and hit-testing

No mouse coordinate conversion is needed. `UpdateBounds` calls the same patched
`ActualLeft`/`ActualWidth` used by drawing and writes physical pixel bounds.
The existing `GUIComponent.IsInBounds` compares physical `Controller.MouseX/Y`
against those bounds. Native GUI cursor coordinates remain physical and can
still reach the full viewport. Cursor graphics already use one uniform scale
for both axes, so they are not horizontally stretched by this patch.

## Scope and integration

This patch does not mutate `Viewport.SizeX/Y`, `Canvas.SizeX/Y`, `Canvas.OrgX/Y`,
the camera, 3D viewport projection, or fullscreen shading. This separates the GUI
layout from a separately scoped HUD/letterboxed-movie adaptation. In particular,
`SHGame.SHMenuBook` renders the book with `Canvas.DrawActor` at source line 38;
that 3D operation stays outside any 2D Canvas wrapper.

The GUI style script drawing path uses the passed native Left/Top/Width/Height.
`STY_SH_FadeStyle.DrawImage` calls Canvas.DrawRect with these dimensions and
`DrawText` uses the same rectangle. No additional screen-width scale was found
in the inspected shipping `STY_SH_*` scripts.

## Verification

`gui-aspect-evidence.json` records execution of the actual patched native
`UpdateBounds`, `ActualLeft`, `ActualWidth`, original top/height methods, and the
font helper in Unicorn:

- 40 geometry cases at 640×480, 800×600, 1024×768, 1280×720, 1366×768,
  1600×900, 1920×1080, 2560×1440, 1280×1024, and 600×800, with both root
  and nested parent-bound components.
- 20 font-selection cases verifying effective font XRes, unchanged Canvas
  dimensions, stack balance, and preserved registers.
- Every case runs at both preferred image base `0x10000000` and rebased image
  `0x20000000` after applying the original PE relocations. This matters because
  the renderer and GUI DLLs share a preferred base in this build.
- Physical inside/outside rectangle checks agree with stored hit-test bounds.

These are native coordinate/font-selection tests, not screenshots or proof of a
complete rendered menu. Visual placement on the 3D book, modal/list clipping,
font legibility at the largest sizes, and real mouse interaction still require
the primary agent's isolated game QA before a final visual-success claim.

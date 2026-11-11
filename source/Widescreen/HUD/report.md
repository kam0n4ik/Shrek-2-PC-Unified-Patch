# HUD widescreen patch evidence

Scope: workspace copies only. No game install, UI input, profile or save changes. The native movie and GUI changes are owned by the parent/other agent. This patch applies a centered 4:3 HUD safe area while preserving the physical fullscreen viewport for 3D rendering, movies, fades and cutscene borders.

## Five function changes

| Package / original export | Evidence in normalized original source | Behavior |
|---|---|---|
| KWGame KWHud.PostRender, export 5578, serial offset 373008, 218→439 bytes | `work/audit/source/KWGame/KWHud.uc:229` | Save Canvas.SizeX/OrgX/ClipX, set SizeX=min(W,int(H*4/3)), center OrgX, bound ClipX. Calculate HUD scales before the HudItems/OverlayPages loops. Restore exact Canvas fields before the original physical scale calculation, CutTextController.RenderHud and Engine.HUD.PostRender. |
| KWGame KWCutTextController.DrawText, export 5633, offset 392700, 451→650 bytes | `work/audit/source/KWGame/KWCutTextController.uc:180` | Independent scoped safe area for subtitle wrap/centering, top commentary and fast-forward icon. The final return always restores exact physical Canvas metrics. |
| SHGame SHHud.DrawLevelAction, export 8204, offset 856681, 873→894 bytes | `work/audit/source/SHGame/SHHud.uc:206` | Change exactly three badge SetPos x expressions and three badge widths. Width=H*256/600, x=W/2-H*128/600; original y/height retained. The full black preamble texture still fills physical W×H. |
| SHGame SHCutTextController.Hourglass.RenderHud, export 8077, offset 804122, 288→290 bytes | `work/audit/source/SHGame/SHCutTextController.uc:7` | X icon scale uses GetScaleY, matching its Y scale. Pixel-valued fCurrBorderHeight=H/2 replaced with base-class normalized values: 0.5 in cutscene (two half-screen borders), 1 otherwise (one full-screen lower border). Both cover the physical fullscreen viewport. |
| SHGame SlotMachine.SlotMachineTakeCoins.CoinWorldLocationFromScreen, export 7374, offset 675551, 163→412 bytes | `work/audit/source/SHGame/SlotMachine.uc:896` | Convert the coin icon's legacy screen x to offset+oldX*safeW/physicalW before the existing KWGetWorldLoc call. It continues passing physical viewport W/H; the flying coin therefore starts at the relocated HUD icon. |

Examples: at 1920×1080 the safe width is 1440 and x offset is 240. At 2560×1440 they are 1920 and 320. At stock 640×480, 800×600 and 1024×768, the horizontal geometry is unchanged. Original pixel fonts retain their glyph proportions; their existing discrete size selection is retained.

## Why the scope matters

SHHud.InitHudItems creates seven 2D items (coins, health, boss health, game timer, potion timer, potion, time-up banner). Their x positions and tile widths use either Canvas.SizeX or KWHud.fScaleX; y uses SizeY/fScaleY. Changing only CalculateScaleX misses the health/boss/timer geometry. The scoped viewport fixes all seven together.

KWHud.fScaleX must be restored to the physical viewport outside drawing: SHHud.GetCanvasSizeX returns int(fScaleX*fBaseResX) and SlotMachine uses it for world unprojection. This patch restores that convention before leaving PostRender.

KWCutTextController.DrawBorder (`:149`) is intentionally unchanged and is called with physical Canvas metrics. Engine.HUD.PostRender is similarly outside the wrapper, so its physical screen fades/movie paths remain available. The 3D SHMenuBook is rendered from GUI ShFEGUIPage rather than the scoped HUD section. The separate GUI native patch does not modify Canvas metrics, so it receives no duplicate transform.

Native evidence from original Engine.dll, independently checked by engine_audit: execDrawTile adds Canvas.OrgX at VA 0x103F5C7B and OrgY at 0x103F5C4D. DrawText's WrappedPrint→DrawString path adds OrgX at 0x103FA4F5 and OrgY at 0x103FA4D9; the bitmap-font path also adds OrgX at 0x103FA7B8. Therefore both tiles and text receive the same safe-area x offset.

## Serialization and preservation

KWGame appends two names (OrgX, ClipX), two FloatProperty imports (-823, -824), and six local UProperty exports (8237…8242). Existing object/import/name indices remain stable. The Children/NextField chains for C→i→Width→X→W and Canvas→Width→X→W are checked from raw serialized properties. Export/name/import tables are rebuilt at the file end; package GUIDs remain unchanged and generation counts reflect new table sizes.

SHGame changes only the three listed function exports; it requires no new names, imports or exports. All branch offsets and nested Context skip lengths are relocated by logical bytecode offsets, accounting for compact serialized refs and two-byte native opcodes. Re-decompilation is saved in `verified/`; replacement blobs and full package copies are in `built/`.

Structural comparison confirms 8232 original KWGame exports and 13539 SHGame exports are byte-identical to their input package exports. This retains the earlier gameplay fixes and video menu patch.

## Checks and limits

`python work/widescreen/hud/test_hud.py` executes actual rebuilt bytecode using a recording Canvas: 225 scenarios passed (144 KW, 81 SH), across all nine supported resolutions. It checks visible/hidden HUD, cutscene item skipping, overlays, exact restoration with nonzero origin and nontrivial clipping, subtitle/comment branches, both FF icon loading paths, loading/saving/preamble background, both hourglass coverage states, and physical slot-machine unprojection. All branch targets and Context skip sizes are valid. See `test-results.json`.

These are bytecode behavioral and package preservation tests; they do not replace the parent's isolated-game visual QA. Custom mods adding generic 3D KWHudFadeSpinItem or 3D OverlayPages would need separate physical-space handling; no such item is registered by this Shrek 2 build. Narrower-than-4:3 modes retain the existing width behavior; the supported target list is 4:3 and 16:9.

Builder usage: `python work/widescreen/hud/build_hud.py --kw INPUT_KWGAME --sh INPUT_SHGAME --out DESTINATION`. Use the gameplay-fixed KWGame and current video-patched SHGame as inputs. `metadata.json` records hashes and complete changed-export metadata; the builder does not import the root build script and has no install side effects.

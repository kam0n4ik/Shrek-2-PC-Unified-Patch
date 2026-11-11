# VSync crash: script-path review

Reviewed installed v1.2 `E:\Shrek 2\System\SHGame.u` SHA-256 `d34ade215dfb3103ce5cd60dc6b4e10fec9ccd2c1f202b862953304c941b271d`, which is identical to `work/widescreen/final/System/SHGame.u`. No game/profile/package changes were made.

**Finding:** choosing VSync Off does not execute the VSync setter or SetRes. The setter runs only after Apply. The confirmed immediate-selection crash occurs in the combo's OnChange delegate dispatch. Static bindings and installed application bytecode are correct; no script callback patch is justified by the evidence.

## Actual selection and application paths

`GUIList.SetIndex` invokes OnChange → GUIComboBox.ItemChanged → GUIEditBox.SetText → GUIComboBox.TextChanged → combo.OnChange(self). GUIEditBox.SetText invokes the callback even for programmatic SetText calls. The expected combo.OnChange target is the owning Tab_OptionsVideo.TabOptions_OnChange function.

Installed `Tab_OptionsVideo.TabOptions_OnChange` export 8093, serial offset 3114735, size 1214: its cbRenderer case only plays the click sound and sets the two Apply visibility flags. It contains no ConsoleCommand, renderer mutation, menu replacement or resolution-list refresh in this case.

Installed `VideoChangeOK.Execute` export 7949, offset 3113937, size 575 runs after Apply has opened its confirmation menu and set videoptr. The command order is:

1. Read and save current UseVSync and actual fullscreen/resolution.
2. Set `ini:Engine.Engine.RenderDevice UseVSync` to True/False according to the selected label.
3. Set Use16bit False and MaxResWidth/Height ceilings.
4. Issue exactly one `setres <width>x<height>x32f/w`.
5. Clear Controller.GameResolution.

Accept issues no second SetRes; decline and timeout restore the saved UseVSync, issue one rollback SetRes and refresh the selectors. StartupFullscreen is persisted after the final mode is known. This order is consistent for same-resolution VSync changes. The VSync False command is syntactically the same property-setting form as the original game's Use16bit setting.

## Binding evidence

The installed InitComponent export 3511 at 3110745 contains the same two raw loop binding instructions as the original, at relocated memory offsets 2418 and 2444 (original 2379 and 2405):

```
45 19 10 00 4e 06 01 f2 02 05 00 08 01 fe 0a 44 56 14
45 19 10 00 4e 06 01 f2 02 05 00 08 01 e3 0d 44 00
```

The first assigns `Controls[i].__OnChange__Delegate`: import -702 resolves to `GUI.GUIComponent.__OnChange__Delegate`, RHS FName index 1302 resolves to `TabOptions_OnChange`. The second clears OnActivate. The raw instructions are byte-identical to the original. Context skip lengths and relocated loop branch targets are valid.

The current GUI.u bytecode initializes List.OnChange→ItemChanged, Edit.OnChange→TextChanged, and List.OnClick→InternalListClick. GUIComboBox.TextChanged has its DelegateFunctionToken at memory 0x14 and ends it at 0x1F, matching the crash's reported 001F. Its delegate property is `GUI.GUIComponent.__OnChange__Delegate`; the callback argument is self.

The three combo templates, SHGUIComboBox class/InitComponent, SHGUIPage.InternalOnClick and ShFEGUIPage.InternalOnClick are byte-identical to the original SHGame.u (see `template-checks.json`). All eight installed VSync application/confirmation/refresh function exports are byte-identical to the reviewed build (see `test-results.json`). No static binding to ShFEGUIPage.InternalOnClick was introduced by this patch.

Independent native GUI review confirms InitializeControls at VA 0x10023110 enumerates GUIComponent ObjectProperties by property flags; it has no bVisible/WinWidth filter. Thus originally hidden cbRenderer is still eligible for initialization and inclusion in Controls. The script MapControls method handles focus links rather than controlling which objects enter Controls.

## Crash evidence and interpretation

`work/vsync/native/game-crash.log` (copied from Documents\Shrek 2\game.log) has its last Enter SetRes at line 355, before the front menu opens at line 376. There is no later renderer reset before the crash.

Lines 386–388 report Accessed None in already deactivated/freed `Transient.ShFEGUIPage0` PlayerOwner and SHGUIPage.InternalOnClick, indicating that the observed callback is reaching a page with Controller=None. Lines 389–396 show execDelegateFunction from SHGUIComboBox2.TextChanged → GUIEditBox2.SetText → GUIList2.SetIndex → InternalListClick. This is before any Apply/VideoChangeOK.Execute entry.

The evidence supports a wrong/stale runtime delegate target. The root's independently confirmed movie temporary-buffer overwrite is a plausible source of heap damage and must be fixed before retesting. The log alone does not prove which write corrupted the delegate, so this report does not claim definitive causality. The native UseVSync/SetRes path cannot explain this immediate selection crash because it has not run.

## Verification and safe next step

`python work/vsync/test_script_path.py`: **212 scenarios passed**: 16 selection-only cases, 192 application/accept/decline/timeout combinations, and 4 empty-request guards. Scenarios include same-resolution VSync Off, fullscreen/window transitions, forwarded programmatic SetText callbacks, and an adversarial synchronous Refresh during mocked SetRes. Each application executes exactly one Execute and one SetRes; callbacks stay bounded, and rollback values/mode persistence are correct. All dumped installed function branch targets and Context skips validate. Native ConsoleCommand and delegate storage are mocked, so these tests do not reproduce or exclude native heap corruption.

Safest release change: repair the proven movie buffer overwrite and retain the reviewed callback binding. Then test selecting Off/On before Apply, applying, confirming, declining and timeout rollback in a clean process. Rebinding an already correct callback or swallowing the stale-page exception would conceal heap damage and is not recommended without new evidence.

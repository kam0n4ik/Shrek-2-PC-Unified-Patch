// Shrek 2 (2004) PC Unified Patch: full key binding tab for Options.
// Strings use the game's Russian font encoding (Cyrillic glyphs in Latin slots).
class Tab_OptionsControls extends Tab_SHOptions;

const NUMACT = 24;
const ROWS = 6;
const NUMPAGES = 4;

var automated GUILabel lblRow0, lblRow1, lblRow2, lblRow3, lblRow4, lblRow5;
var automated GUIButton btnRow0, btnRow1, btnRow2, btnRow3, btnRow4, btnRow5;
var automated GUIButton btnPrev, btnNext, btnReset;
var automated GUILabel lblPage;

var GUILabel RowLabel[6];
var GUIButton RowButton[6];

var string ActLabel[24];
var string ActCmd[24];
var string ActMatch[24];
var string PageTitle[4];
var string DefKey[48];
var string DefBind[48];

var int ActKey1[24];
var int ActKey2[24];
var string EngKeyName[255];
var string KeyBind[255];

var int Page;
var bool bPolling;
var int PollRow;
var bool bSuppressClick;

var string OrString, NoneString, PressString, RowHint, PrevCaption, NextCaption;
var float RowTop, RowStep, RowHeight, LabelLeft, LabelWidth, ButtonLeft, ButtonWidth, NavTop;

function InitComponent(GUIController MyController, GUIComponent MyOwner)
{
	local int i;

	Super.InitComponent(MyController, MyOwner);

	RowLabel[0] = lblRow0; RowButton[0] = btnRow0;
	RowLabel[1] = lblRow1; RowButton[1] = btnRow1;
	RowLabel[2] = lblRow2; RowButton[2] = btnRow2;
	RowLabel[3] = lblRow3; RowButton[3] = btnRow3;
	RowLabel[4] = lblRow4; RowButton[4] = btnRow4;
	RowLabel[5] = lblRow5; RowButton[5] = btnRow5;

	for (i = 0; i < ROWS; i++)
	{
		RowLabel[i].WinLeft = LabelLeft;
		RowLabel[i].WinWidth = LabelWidth;
		RowLabel[i].WinHeight = RowHeight;
		RowLabel[i].WinTop = RowTop + RowStep * i;
		RowButton[i].WinLeft = ButtonLeft;
		RowButton[i].WinWidth = ButtonWidth;
		RowButton[i].WinHeight = RowHeight;
		RowButton[i].WinTop = RowTop + RowStep * i;
		RowButton[i].Hint = RowHint;
		RowButton[i].OnClick = RowClick;
		RowButton[i].OnKeyEvent = RowKeyEvent;
	}

	btnPrev.WinLeft = LabelLeft;
	btnPrev.WinWidth = 0.12;
	btnPrev.WinHeight = RowHeight;
	btnPrev.WinTop = NavTop;
	btnPrev.Caption = PrevCaption;
	btnPrev.OnClick = NavClick;

	lblPage.WinLeft = LabelLeft + 0.13;
	lblPage.WinWidth = (ButtonLeft + ButtonWidth) - (LabelLeft + 0.26);
	lblPage.WinHeight = RowHeight;
	lblPage.WinTop = NavTop;

	btnNext.WinLeft = (ButtonLeft + ButtonWidth) - 0.12;
	btnNext.WinWidth = 0.12;
	btnNext.WinHeight = RowHeight;
	btnNext.WinTop = NavTop;
	btnNext.Caption = NextCaption;
	btnNext.OnClick = NavClick;

	btnReset.WinWidth = 0.25;
	btnReset.WinHeight = 0.05;
	btnReset.WinLeft = 0.5 - 0.125;
	btnReset.WinTop = 0.6916667;
	btnReset.Caption = Localize("All", "menuitems_166", "HPMenu");
	btnReset.Hint = Localize("All", "menuitems_167", "HPMenu");
	btnReset.OnClick = NavClick;

	OrString = " " $ Localize("All", "menuitems_91", "HPMenu") $ " ";
	NoneString = Localize("All", "menuitems_168", "HPMenu");

	for (i = 0; i < 255; i++)
		EngKeyName[i] = PlayerOwner().ConsoleCommand("KEYNAME " $ i);

	Page = 0;
	bPolling = false;
	LoadBindings();
	ShowPage();
}

function ShowPanel(bool bShow)
{
	local int i;

	Super.ShowPanel(bShow);
	if (bShow)
	{
		for (i = 0; i < Controls.Length; i++)
			Controls[i].bVisible = true;
		bPolling = false;
		LoadBindings();
		ShowPage();
	}
	else
		bPolling = false;
}

function RefreshPage()
{
	local int i;

	for (i = 0; i < Controls.Length; i++)
		Controls[i].bVisible = true;
}

// ---------- strings ----------

function string Trim(string S)
{
	while (Len(S) > 0 && (Left(S, 1) == " " || Left(S, 1) == Chr(9)))
		S = Mid(S, 1);
	while (Len(S) > 0 && (Right(S, 1) == " " || Right(S, 1) == Chr(9)))
		S = Left(S, Len(S) - 1);
	return S;
}

function string NormToken(string S)
{
	local int i;

	S = Caps(Trim(S));
	i = InStr(S, "  ");
	while (i >= 0)
	{
		S = Left(S, i) $ Mid(S, i + 1);
		i = InStr(S, "  ");
	}
	return S;
}

function bool TokenIsAction(string Tok, int A)
{
	local string L, Item;
	local int i;

	Tok = NormToken(Tok);
	if (Tok == "")
		return false;
	L = ActMatch[A];
	while (L != "")
	{
		i = InStr(L, ";");
		if (i < 0)
		{
			Item = L;
			L = "";
		}
		else
		{
			Item = Left(L, i);
			L = Mid(L, i + 1);
		}
		if (Tok == Item)
			return true;
	}
	return false;
}

function bool BindHasAction(string B, int A)
{
	local int i;

	while (B != "")
	{
		i = InStr(B, "|");
		if (i < 0)
			return TokenIsAction(B, A);
		if (TokenIsAction(Left(B, i), A))
			return true;
		B = Mid(B, i + 1);
	}
	return false;
}

function string RemoveAction(string B, int A)
{
	local string Out, Tok;
	local int i;

	Out = "";
	while (B != "")
	{
		i = InStr(B, "|");
		if (i < 0)
		{
			Tok = B;
			B = "";
		}
		else
		{
			Tok = Left(B, i);
			B = Mid(B, i + 1);
		}
		Tok = Trim(Tok);
		if (Tok == "" || TokenIsAction(Tok, A))
			continue;
		if (Out == "")
			Out = Tok;
		else
			Out = Out $ " | " $ Tok;
	}
	return Out;
}

function bool PrimaryOnKey(string B, int A)
{
	local int i;
	local string P;

	P = NormToken(ActCmd[A]);
	while (B != "")
	{
		i = InStr(B, "|");
		if (i < 0)
			return NormToken(B) == P;
		if (NormToken(Left(B, i)) == P)
			return true;
		B = Mid(B, i + 1);
	}
	return false;
}

// ---------- bindings ----------

function bool Bindable(int K)
{
	if (K <= 0 || K >= 255 || EngKeyName[K] == "")
		return false;
	if (K == 228 || K == 229)
		return false;
	return true;
}

function LoadBindings()
{
	local int K, A, Pass;

	for (K = 0; K < 255; K++)
	{
		if (Bindable(K))
			KeyBind[K] = PlayerOwner().ConsoleCommand("KEYBINDING " $ EngKeyName[K]);
		else
			KeyBind[K] = "";
	}
	for (A = 0; A < NUMACT; A++)
	{
		ActKey1[A] = -1;
		ActKey2[A] = -1;
	}
	for (Pass = 0; Pass < 2; Pass++)
		for (K = 1; K < 255; K++)
		{
			if (KeyBind[K] == "")
				continue;
			for (A = 0; A < NUMACT; A++)
			{
				if (K == ActKey1[A] || K == ActKey2[A])
					continue;
				if (Pass == 0 && !PrimaryOnKey(KeyBind[K], A))
					continue;
				if (Pass == 1 && !BindHasAction(KeyBind[K], A))
					continue;
				if (ActKey1[A] < 0)
					ActKey1[A] = K;
				else if (ActKey2[A] < 0)
					ActKey2[A] = K;
			}
		}
}

function SetBind(int K, string V)
{
	KeyBind[K] = V;
	PlayerOwner().ConsoleCommand("SET Input " $ EngKeyName[K] $ " " $ V);
}

function SaveBindings()
{
	LoadBindings();
	ShowPage();
}

function AssignKey(int A, int K)
{
	local int Keep, K2;

	if (K == ActKey1[A])
		Keep = ActKey2[A];
	else
		Keep = ActKey1[A];
	SetBind(K, ActCmd[A]);
	for (K2 = 1; K2 < 255; K2++)
	{
		if (K2 == K || K2 == Keep || KeyBind[K2] == "")
			continue;
		if (BindHasAction(KeyBind[K2], A))
			SetBind(K2, RemoveAction(KeyBind[K2], A));
	}
	SaveBindings();
}

function ClearAction(int A)
{
	local int K;

	for (K = 1; K < 255; K++)
		if (KeyBind[K] != "" && BindHasAction(KeyBind[K], A))
			SetBind(K, RemoveAction(KeyBind[K], A));
}

function int KeyIndex(string N)
{
	local int K;

	for (K = 1; K < 255; K++)
		if (EngKeyName[K] ~= N)
			return K;
	return -1;
}

function ResetDefaults()
{
	local int A, i, K;

	for (A = 0; A < NUMACT; A++)
		ClearAction(A);
	for (i = 0; i < 48; i++)
	{
		if (DefKey[i] == "")
			continue;
		K = KeyIndex(DefKey[i]);
		if (K > 0)
			SetBind(K, DefBind[i]);
	}
	SaveBindings();
}

// ---------- display ----------

function string KnId(int K)
{
	switch (K)
	{
		case 0: return "404";
		case 12: return "406";
		case 20: return "407";
		case 91: return "408";
		case 92: return "409";
		case 93: return "410";
		case 185: return "421";
		case 193: return "422";
		case 194: return "423";
		case 195: return "424";
		case 196: return "425";
		case 197: return "426";
		case 224: return "427";
		case 225: return "427";
		case 226: return "427";
		case 227: return "427";
		case 234: return "431";
		case 235: return "432";
		case 236: return "433";
		case 237: return "434";
		case 240: return "0224";
		case 241: return "0225";
		case 242: return "0226";
		case 243: return "0227";
	}
	if (K >= 112 && K <= 121)
		return string(299 + K);
	if (K < 10)
		return "000" $ K;
	if (K < 100)
		return "00" $ K;
	return "0" $ K;
}

function string KeyLabel(int K)
{
	local string S;

	S = Localize("All", "Localized_kn_" $ KnId(K), "HPMenu");
	if (S == "" || InStr(S, "<?") >= 0 || InStr(S, "?>") >= 0)
		S = EngKeyName[K];
	return S;
}

function ShowPage()
{
	local int r, A;

	for (r = 0; r < ROWS; r++)
	{
		A = Page * ROWS + r;
		RowLabel[r].Caption = ActLabel[A];
		if (bPolling && r == PollRow)
			RowButton[r].Caption = PressString;
		else if (ActKey1[A] < 0)
			RowButton[r].Caption = NoneString;
		else if (ActKey2[A] < 0)
			RowButton[r].Caption = KeyLabel(ActKey1[A]);
		else
			RowButton[r].Caption = KeyLabel(ActKey1[A]) $ OrString $ KeyLabel(ActKey2[A]);
	}
	lblPage.Caption = PageTitle[Page] $ " (" $ (Page + 1) $ "/" $ NUMPAGES $ ")";
}

// ---------- input ----------

function int RowOf(GUIComponent C)
{
	local int r;

	for (r = 0; r < ROWS; r++)
		if (RowButton[r] == C)
			return r;
	return -1;
}

function bool RowClick(GUIComponent Sender)
{
	local int r;

	if (bSuppressClick)
	{
		bSuppressClick = false;
		return true;
	}
	r = RowOf(Sender);
	if (r < 0)
		return false;
	if (bPolling && r == PollRow)
	{
		bPolling = false;
		AssignKey(Page * ROWS + r, 1);
		return true;
	}
	PlayerOwner().PlaySound(sfxClick);
	bPolling = true;
	PollRow = r;
	ShowPage();
	return true;
}

function bool RowKeyEvent(out byte Key, out byte State, float Delta)
{
	local int K;

	if (!bPolling)
		return false;
	if (State != 1)
		return true;
	K = Key;
	if (K == 27)
	{
		bPolling = false;
		ShowPage();
		return true;
	}
	if (K == 8)
	{
		bPolling = false;
		ClearAction(Page * ROWS + PollRow);
		SaveBindings();
		return true;
	}
	if (!Bindable(K))
		return true;
	if (K == 1)
		bSuppressClick = true;
	bPolling = false;
	AssignKey(Page * ROWS + PollRow, K);
	return true;
}

function bool NavClick(GUIComponent Sender)
{
	bPolling = false;
	bSuppressClick = false;
	PlayerOwner().PlaySound(sfxClick);
	if (Sender == btnPrev)
	{
		Page--;
		if (Page < 0)
			Page = NUMPAGES - 1;
	}
	else if (Sender == btnNext)
	{
		Page++;
		if (Page >= NUMPAGES)
			Page = 0;
	}
	else if (Sender == btnReset)
	{
		ResetDefaults();
		return true;
	}
	ShowPage();
	return true;
}

defaultproperties
{
	Begin Object Class=GUILabel Name=cLblRow0
		StyleName="SHOptionLabel"
	End Object
	lblRow0=GUILabel'cLblRow0'
	Begin Object Class=GUILabel Name=cLblRow1
		StyleName="SHOptionLabel"
	End Object
	lblRow1=GUILabel'cLblRow1'
	Begin Object Class=GUILabel Name=cLblRow2
		StyleName="SHOptionLabel"
	End Object
	lblRow2=GUILabel'cLblRow2'
	Begin Object Class=GUILabel Name=cLblRow3
		StyleName="SHOptionLabel"
	End Object
	lblRow3=GUILabel'cLblRow3'
	Begin Object Class=GUILabel Name=cLblRow4
		StyleName="SHOptionLabel"
	End Object
	lblRow4=GUILabel'cLblRow4'
	Begin Object Class=GUILabel Name=cLblRow5
		StyleName="SHOptionLabel"
	End Object
	lblRow5=GUILabel'cLblRow5'

	Begin Object Class=GUIButton Name=cBtnRow0
		StyleName="SHSolidBox"
	End Object
	btnRow0=GUIButton'cBtnRow0'
	Begin Object Class=GUIButton Name=cBtnRow1
		StyleName="SHSolidBox"
	End Object
	btnRow1=GUIButton'cBtnRow1'
	Begin Object Class=GUIButton Name=cBtnRow2
		StyleName="SHSolidBox"
	End Object
	btnRow2=GUIButton'cBtnRow2'
	Begin Object Class=GUIButton Name=cBtnRow3
		StyleName="SHSolidBox"
	End Object
	btnRow3=GUIButton'cBtnRow3'
	Begin Object Class=GUIButton Name=cBtnRow4
		StyleName="SHSolidBox"
	End Object
	btnRow4=GUIButton'cBtnRow4'
	Begin Object Class=GUIButton Name=cBtnRow5
		StyleName="SHSolidBox"
	End Object
	btnRow5=GUIButton'cBtnRow5'

	Begin Object Class=GUIButton Name=cBtnPrev
		StyleName="SHSolidBox"
	End Object
	btnPrev=GUIButton'cBtnPrev'
	Begin Object Class=GUIButton Name=cBtnNext
		StyleName="SHSolidBox"
	End Object
	btnNext=GUIButton'cBtnNext'
	Begin Object Class=GUIButton Name=cBtnReset
		StyleName="SHSolidBox"
	End Object
	btnReset=GUIButton'cBtnReset'
	Begin Object Class=GUILabel Name=cLblPage
		StyleName="SHOptionLabel"
		TextAlign=TXTA_Center
	End Object
	lblPage=GUILabel'cLblPage'

	RowTop=0.038333
	RowStep=0.060075
	RowHeight=0.05
	LabelLeft=0.2625
	LabelWidth=0.165
	ButtonLeft=0.4375
	ButtonWidth=0.29625
	NavTop=0.4533333

	PressString="HAGMNTE KLABNWY"
	RowHint="WELKHNTE N HAGMNTE KLABNWY. backspace - O4NCTNTJ, escape - OTMEHA"
	PrevCaption="HA3AD"
	NextCaption="DALEE"

	PageTitle(0)="DBNGEHNE"
	PageTitle(1)="KAMEPA"
	PageTitle(2)="3ELJR"
	PageTitle(3)="3ELJR N MEHU"

	ActLabel(0)="BZEPED"
	ActCmd(0)="MoveForward"
	ActMatch(0)="MOVEFORWARD;AXIS AARROWUP SPEEDBASE=0.7"
	ActLabel(1)="HA3AD"
	ActCmd(1)="MoveBackward"
	ActMatch(1)="MOVEBACKWARD;AXIS AARROWUP SPEEDBASE=0.7 INVERT=-1"
	ActLabel(2)="BLEBO"
	ActCmd(2)="StrafeLeft"
	ActMatch(2)="STRAFELEFT"
	ActLabel(3)="BZPABO"
	ActCmd(3)="StrafeRight"
	ActMatch(3)="STRAFERIGHT"
	ActLabel(4)="ZPSGOK"
	ActCmd(4)="Jump"
	ActMatch(4)="JUMP"
	ActLabel(5)="ATAKA"
	ActCmd(5)="Fire"
	ActMatch(5)="FIRE"

	ActLabel(6)="KAMEPA BLEBO"
	ActCmd(6)="TurnLeft"
	ActMatch(6)="TURNLEFT;AXIS AARROWRIGHT SPEEDBASE=0.9 INVERT=-1"
	ActLabel(7)="KAMEPA BZPABO"
	ActCmd(7)="TurnRight"
	ActMatch(7)="TURNRIGHT;AXIS AARROWRIGHT SPEEDBASE=0.9 INVERT=1"
	ActLabel(8)="QEHTP KAMEPS"
	ActCmd(8)="CenterView"
	ActMatch(8)="CENTERVIEW"
	ActLabel(9)="ABTOKAMEPA"
	ActCmd(9)="ToggleAutoLeveling"
	ActMatch(9)="TOGGLEAUTOLEVELING"
	ActLabel(10)="ZOBOPOT K BPAFY"
	ActCmd(10)="TurnToNearest"
	ActMatch(10)="TURNTONEAREST"
	ActLabel(11)="PA3BOPOT"
	ActCmd(11)="Turn180"
	ActMatch(11)="TURN180"

	ActLabel(12)="3ELJE 1"
	ActCmd(12)="SelectPotion 0"
	ActMatch(12)="SELECTPOTION 0"
	ActLabel(13)="3ELJE 2"
	ActCmd(13)="SelectPotion 1"
	ActMatch(13)="SELECTPOTION 1"
	ActLabel(14)="3ELJE 3"
	ActCmd(14)="SelectPotion 2"
	ActMatch(14)="SELECTPOTION 2"
	ActLabel(15)="3ELJE 4"
	ActCmd(15)="SelectPotion 3"
	ActMatch(15)="SELECTPOTION 3"
	ActLabel(16)="3ELJE 5"
	ActCmd(16)="SelectPotion 4"
	ActMatch(16)="SELECTPOTION 4"
	ActLabel(17)="3ELJE 6"
	ActCmd(17)="SelectPotion 5"
	ActMatch(17)="SELECTPOTION 5"
	ActLabel(18)="3ELJE 7"
	ActCmd(18)="SelectPotion 6"
	ActMatch(18)="SELECTPOTION 6"
	ActLabel(19)="3ELJE 8"
	ActCmd(19)="SelectPotion 7"
	ActMatch(19)="SELECTPOTION 7"
	ActLabel(20)="3ELJE 9"
	ActCmd(20)="SelectPotion 8"
	ActMatch(20)="SELECTPOTION 8"
	ActLabel(21)="MEHU 3ELNN"
	ActCmd(21)="BypassCutscene | StopMoviePlayback"
	ActMatch(21)="STOPMOVIEPLAYBACK;BYPASSCUTSCENE"
	ActLabel(22)="ZAY3A"
	ActCmd(22)="Pause"
	ActMatch(22)="PAUSE"
	ActLabel(23)="MEHU NFPS"
	ActCmd(23)="EscHandler"
	ActMatch(23)="ESCHANDLER"

	DefKey(0)="W"
	DefBind(0)="MoveForward"
	DefKey(1)="Up"
	DefBind(1)="Axis aArrowUp SpeedBase=0.7"
	DefKey(2)="S"
	DefBind(2)="MoveBackward"
	DefKey(3)="Down"
	DefBind(3)="Axis aArrowUp SpeedBase=0.7 Invert=-1"
	DefKey(4)="A"
	DefBind(4)="StrafeLeft"
	DefKey(5)="D"
	DefBind(5)="StrafeRight"
	DefKey(6)="RightMouse"
	DefBind(6)="Jump"
	DefKey(7)="Ctrl"
	DefBind(7)="Jump"
	DefKey(8)="LeftMouse"
	DefBind(8)="Fire"
	DefKey(9)="Enter"
	DefBind(9)="Use | Fire"
	DefKey(10)="Left"
	DefBind(10)="Axis aArrowRight SpeedBase=0.9 Invert=-1"
	DefKey(11)="Right"
	DefBind(11)="Axis aArrowRight SpeedBase=0.9 Invert=1"
	DefKey(12)="Home"
	DefBind(12)="CenterView | ACTOR ALIGN SNAPTOFLOOR ALIGN=0"
	DefKey(13)="End"
	DefBind(13)="CenterView | ACTOR ALIGN SNAPTOFLOOR ALIGN=1 | | FreeCam"
	DefKey(14)="B"
	DefBind(14)="ToggleAutoLeveling"
	DefKey(15)="O"
	DefBind(15)="TurnToNearest"
	DefKey(16)="1"
	DefBind(16)="SelectPotion 0"
	DefKey(17)="2"
	DefBind(17)="SelectPotion 1"
	DefKey(18)="3"
	DefBind(18)="SelectPotion 2"
	DefKey(19)="4"
	DefBind(19)="SelectPotion 3"
	DefKey(20)="5"
	DefBind(20)="SelectPotion 4"
	DefKey(21)="6"
	DefBind(21)="SelectPotion 5"
	DefKey(22)="7"
	DefBind(22)="SelectPotion 6"
	DefKey(23)="8"
	DefBind(23)="SelectPotion 7"
	DefKey(24)="9"
	DefBind(24)="SelectPotion 8"
	DefKey(25)="NumPad1"
	DefBind(25)="SelectPotion 0"
	DefKey(26)="NumPad2"
	DefBind(26)="SelectPotion 1"
	DefKey(27)="NumPad3"
	DefBind(27)="SelectPotion 2"
	DefKey(28)="NumPad4"
	DefBind(28)="SelectPotion 3"
	DefKey(29)="NumPad5"
	DefBind(29)="SelectPotion 4"
	DefKey(30)="NumPad6"
	DefBind(30)="SelectPotion 5"
	DefKey(31)="NumPad7"
	DefBind(31)="SelectPotion 6"
	DefKey(32)="NumPad8"
	DefBind(32)="SelectPotion 7"
	DefKey(33)="NumPad9"
	DefBind(33)="SelectPotion 8"
	DefKey(34)="Space"
	DefBind(34)="BypassCutscene | StopMoviePlayback"
	DefKey(35)="Pause"
	DefBind(35)="Pause"
	DefKey(36)="Escape"
	DefBind(36)="EscHandler"

	WinTop=0.25
	WinHeight=0.74
}

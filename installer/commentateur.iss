; Installeur Inno Setup de Commentateur C.
; Construction : installer\build.bat (ou ISCC.exe installer\commentateur.iss)
; Resultat : dist\Commentateur-C-Setup-<version>.exe

#define AppName "Commentateur C"
#define AppVersion "1.0.0"
#define AppPublisher "Vincent Moinet"
#define PythonMin "3.8"
#define PythonMinTuple "3, 8"

[Setup]
AppId={{6F1C2B7E-4A0D-4C8E-9B3F-2E5D7A1C9F40}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Pas besoin des droits administrateur : installation dans le profil par defaut.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=commentateur.ico
UninstallDisplayIcon={app}\commentateur.ico
UninstallDisplayName={#AppName}
OutputDir=..\dist
OutputBaseFilename=Commentateur-C-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "..\commenter_code.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "commentateur.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{code:GetPythonW}"; Parameters: """{app}\commenter_code.py"""; WorkingDir: "{userdocs}"; IconFilename: "{app}\commentateur.ico"; Comment: "Commenter du code C avec Ollama"; AppUserModelID: "CommentateurC.Ollama"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{code:GetPythonW}"; Parameters: """{app}\commenter_code.py"""; WorkingDir: "{userdocs}"; IconFilename: "{app}\commentateur.ico"; Comment: "Commenter du code C avec Ollama"; AppUserModelID: "CommentateurC.Ollama"; Tasks: desktopicon

[Run]
Filename: "{code:GetPythonW}"; Parameters: """{app}\commenter_code.py"""; WorkingDir: "{userdocs}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
var
  PagePython: TWizardPage;
  LabelEtat: TNewStaticText;
  BoutonWinget, BoutonSite, BoutonVerifier: TNewButton;
  PythonW: String;      { pythonw.exe retenu pour les raccourcis }
  PythonVersion: String;

function GetPythonW(Param: String): String;
begin
  Result := PythonW;
end;

{ "3.13", "3.13-32", "3.14t"... -> majeur et mineur }
procedure LireVersion(S: String; var Majeur, Mineur: Integer);
var
  P, I: Integer;
  Reste: String;
begin
  Majeur := 0;
  Mineur := 0;
  P := Pos('.', S);
  if P = 0 then Exit;
  Majeur := StrToIntDef(Copy(S, 1, P - 1), 0);
  Reste := Copy(S, P + 1, Length(S));
  I := 1;
  while (I <= Length(Reste)) and (Reste[I] >= '0') and (Reste[I] <= '9') do
    I := I + 1;
  Mineur := StrToIntDef(Copy(Reste, 1, I - 1), 0);
end;

function VersionSuffisante(Majeur, Mineur: Integer): Boolean;
var
  MinMaj, MinMin: Integer;
begin
  LireVersion('{#PythonMin}', MinMaj, MinMin);
  Result := (Majeur > MinMaj) or ((Majeur = MinMaj) and (Mineur >= MinMin));
end;

{ Lance python.exe pour verifier la version et la presence de Tkinter. }
function PythonFonctionne(PyW: String): Boolean;
var
  PyExe: String;
  Code: Integer;
begin
  Result := False;
  if not FileExists(PyW) then Exit;
  PyExe := ExtractFilePath(PyW) + 'python.exe';
  if not FileExists(PyExe) then PyExe := PyW;
  Result := Exec(PyExe,
    '-c "import sys, tkinter; sys.exit(0 if sys.version_info >= ({#PythonMinTuple}) else 3)"',
    '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

{ Parcourt les installations declarees dans le registre (PEP 514). }
procedure ChercherDans(Racine: Integer; var MeilleurMaj, MeilleurMin: Integer);
var
  Versions: TArrayOfString;
  I, Maj, Min: Integer;
  Cle, Chemin: String;
begin
  if not RegGetSubkeyNames(Racine, 'Software\Python\PythonCore', Versions) then Exit;
  for I := 0 to GetArrayLength(Versions) - 1 do
  begin
    LireVersion(Versions[I], Maj, Min);
    if not VersionSuffisante(Maj, Min) then Continue;
    if (Maj < MeilleurMaj) or ((Maj = MeilleurMaj) and (Min <= MeilleurMin)) then Continue;
    Cle := 'Software\Python\PythonCore\' + Versions[I] + '\InstallPath';
    if not RegQueryStringValue(Racine, Cle, 'WindowedExecutablePath', Chemin) then
    begin
      if RegQueryStringValue(Racine, Cle, '', Chemin) then
        Chemin := AddBackslash(Chemin) + 'pythonw.exe'
      else
        Chemin := '';
    end;
    if (Chemin <> '') and PythonFonctionne(Chemin) then
    begin
      PythonW := Chemin;
      PythonVersion := Versions[I];
      MeilleurMaj := Maj;
      MeilleurMin := Min;
    end;
  end;
end;

{ Repli : le lanceur "py" de Windows. }
procedure ChercherViaLanceur();
var
  Tmp, Sortie: String;
  Lignes: TArrayOfString;
  Code: Integer;
begin
  Tmp := ExpandConstant('{tmp}\python_trouve.txt');
  if Exec(ExpandConstant('{cmd}'),
      '/C py -3 -c "import sys, tkinter, os; print(os.path.join(sys.exec_prefix, ''pythonw.exe'')); print(''%d.%d'' % sys.version_info[:2])" > "' + Tmp + '"',
      '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0)
     and LoadStringsFromFile(Tmp, Lignes) and (GetArrayLength(Lignes) >= 2) then
  begin
    Sortie := Trim(Lignes[0]);
    if PythonFonctionne(Sortie) then
    begin
      PythonW := Sortie;
      PythonVersion := Trim(Lignes[1]);
    end;
  end;
end;

procedure DetecterPython();
var
  Maj, Min: Integer;
begin
  PythonW := '';
  PythonVersion := '';
  Maj := 0;
  Min := 0;
  ChercherDans(HKCU, Maj, Min);
  if IsWin64 then ChercherDans(HKLM64, Maj, Min);
  ChercherDans(HKLM32, Maj, Min);
  if PythonW = '' then ChercherViaLanceur();
end;

procedure MettreAJourPage();
var
  Ok: Boolean;
begin
  Ok := PythonW <> '';
  if Ok then
    LabelEtat.Caption :=
      'Python ' + PythonVersion + ' a été trouvé et fonctionne (Tkinter inclus) :' + #13#10 +
      PythonW + #13#10#13#10 + 'Cliquez sur Suivant pour continuer.'
  else
    LabelEtat.Caption :=
      'Aucun Python compatible n''a été trouvé (version {#PythonMin} ou plus récente, avec Tkinter).' + #13#10#13#10 +
      'Vous pouvez l''installer automatiquement avec winget, ou le télécharger depuis python.org ' +
      '(gardez cochée l''option "tcl/tk and IDLE"). Cliquez ensuite sur "Vérifier à nouveau".';
  BoutonWinget.Visible := not Ok;
  BoutonSite.Visible := not Ok;
  WizardForm.NextButton.Enabled := Ok;
end;

procedure SurVerifier(Sender: TObject);
begin
  LabelEtat.Caption := 'Recherche de Python en cours...';
  WizardForm.Refresh;
  DetecterPython();
  MettreAJourPage();
end;

procedure SurWinget(Sender: TObject);
var
  Code: Integer;
begin
  LabelEtat.Caption := 'Installation de Python 3.13 via winget... une fenêtre de console va s''ouvrir, patientez.';
  WizardForm.Refresh;
  if not Exec(ExpandConstant('{cmd}'),
      '/C winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements',
      '', SW_SHOW, ewWaitUntilTerminated, Code) or (Code <> 0) then
    MsgBox('L''installation via winget n''a pas abouti (code ' + IntToStr(Code) + ').' + #13#10 +
           'Utilisez le bouton "Télécharger depuis python.org".', mbError, MB_OK);
  SurVerifier(Sender);
end;

procedure SurSite(Sender: TObject);
var
  Code: Integer;
begin
  ShellExec('open', 'https://www.python.org/downloads/windows/', '', '', SW_SHOWNORMAL, ewNoWait, Code);
end;

function NouveauBouton(Texte: String; Gauche, Haut, Largeur: Integer; Clic: TNotifyEvent): TNewButton;
begin
  Result := TNewButton.Create(PagePython);
  Result.Parent := PagePython.Surface;
  Result.Caption := Texte;
  Result.Left := Gauche;
  Result.Top := Haut;
  Result.Width := Largeur;
  Result.Height := ScaleY(25);
  Result.OnClick := Clic;
end;

procedure InitializeWizard();
var
  Largeur: Integer;
begin
  PagePython := CreateCustomPage(wpWelcome, 'Vérification de Python',
    '{#AppName} a besoin de Python {#PythonMin} (ou plus récent) avec Tkinter.');

  LabelEtat := TNewStaticText.Create(PagePython);
  LabelEtat.Parent := PagePython.Surface;
  LabelEtat.Width := PagePython.SurfaceWidth;
  LabelEtat.AutoSize := False;
  LabelEtat.WordWrap := True;
  LabelEtat.Height := ScaleY(110);

  Largeur := (PagePython.SurfaceWidth - ScaleX(16)) div 3;
  BoutonWinget := NouveauBouton('Installer Python (winget)', 0, ScaleY(125), Largeur, @SurWinget);
  BoutonSite := NouveauBouton('Télécharger depuis python.org', Largeur + ScaleX(8), ScaleY(125), Largeur, @SurSite);
  BoutonVerifier := NouveauBouton('Vérifier à nouveau', 2 * (Largeur + ScaleX(8)), ScaleY(125), Largeur, @SurVerifier);

  DetecterPython();
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = PagePython.ID then
    MettreAJourPage()
  else if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 +
      'Rappel : Ollama doit être lancé et le modèle installé (ollama pull mistral:7b).';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = PagePython.ID) and (PythonW = '') then
  begin
    MsgBox('Installez d''abord Python, puis cliquez sur "Vérifier à nouveau".', mbInformation, MB_OK);
    Result := False;
  end;
end;

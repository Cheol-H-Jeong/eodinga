; eodinga Windows installer
#define AppName "eodinga"
#define AppVersion "@@APP_VERSION@@"
#define AppPublisher "Cheol-H-Jeong"
#define AppId "{{B4D25A04-71A1-45A2-A0BB-7B3F612E9E68}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={userappdata}\eodinga
DefaultGroupName=eodinga
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=eodinga-{#AppVersion}-win-x64-setup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\@@GUI_EXE_NAME@@
LicenseFile=LICENSE
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "autostart"; Description: "{cm:LaunchAtStartup,en} / {cm:LaunchAtStartup,ko}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[Files]
Source: "dist\\@@GUI_DIST_NAME@@\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\\@@CLI_DIST_NAME@@\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueType: string; ValueName: "eodinga"; ValueData: """{app}\\@@GUI_EXE_NAME@@"""; Flags: uninsdeletevalue; Tasks: autostart

[Icons]
Name: "{group}\\eodinga"; Filename: "{app}\\@@GUI_EXE_NAME@@"
Name: "{userdesktop}\\eodinga"; Filename: "{app}\\@@GUI_EXE_NAME@@"; Tasks: desktopicon

[Run]
Filename: "{app}\\@@GUI_EXE_NAME@@"; Description: "{cm:LaunchProgram,eodinga}"; Flags: nowait postinstall skipifsilent

[Code]
procedure PurgeUserState();
begin
  DelTree(ExpandConstant('{localappdata}\\eodinga'), True, True, True);
  DelTree(ExpandConstant('{userappdata}\\eodinga'), True, True, True);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Purge %LOCALAPPDATA%\\eodinga and %APPDATA%\\eodinga? / %LOCALAPPDATA%\\eodinga 및 %APPDATA%\\eodinga 데이터를 삭제할까요?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      PurgeUserState();
    end;
  end;
end;

[CustomMessages]
english.LaunchAtStartup=Launch eodinga at login
korean.LaunchAtStartup=로그인 시 eodinga 자동 실행

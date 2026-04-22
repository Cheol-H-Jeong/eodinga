; eodinga Windows installer
#define AppName "eodinga"
#define AppVersion "0.1.0"
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
OutputBaseFilename=eodinga-setup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\eodinga-gui.exe
LicenseFile=LICENSE
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "autostart"; Description: "{cm:LaunchAtStartup,en} / {cm:LaunchAtStartup,ko}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[Files]
Source: "dist\\eodinga-gui\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\\eodinga-cli\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\eodinga"; Filename: "{app}\\eodinga-gui.exe"
Name: "{commondesktop}\\eodinga"; Filename: "{app}\\eodinga-gui.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\\eodinga-gui.exe"; Description: "{cm:LaunchProgram,eodinga}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Purge %LOCALAPPDATA%\\eodinga\\ data? / %LOCALAPPDATA%\\eodinga\\ 데이터를 삭제할까요?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{localappdata}\\eodinga'), True, True, True);
    end;
  end;
end;

[CustomMessages]
english.LaunchAtStartup=Launch eodinga at login
korean.LaunchAtStartup=로그인 시 eodinga 자동 실행


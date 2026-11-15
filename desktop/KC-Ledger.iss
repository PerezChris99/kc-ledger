; Per-user installer. Personal database and logs are not removed by uninstall.
#define MyAppName "KC Ledger"
#define MyAppVersion "0.1.0"

[Setup]
AppId={{71130585-D271-4147-86AD-0AA204FC73CE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\KC Ledger
DefaultGroupName=KC Ledger
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\KC Ledger.exe
OutputDir=..\installer-output
OutputBaseFilename=KC-Ledger-Setup-0.1.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
ArchitecturesAllowed=x64

[Files]
Source: "..\dist\KC Ledger\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

Source: "..\desktop\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\KC Ledger"; Filename: "{app}\KC Ledger.exe"
Name: "{autodesktop}\KC Ledger"; Filename: "{app}\KC Ledger.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft WebView2 Runtime..."; Check: not WebView2Installed
Filename: "{app}\KC Ledger.exe"; Description: "Launch KC Ledger"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed(): Boolean;
var
  Ver: string;
begin
  Result :=
    (RegQueryStringValue(HKCU,
      'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Ver) and (Ver <> '') and (Ver <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM,
      'Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Ver) and (Ver <> '') and (Ver <> '0.0.0.0'));
end;

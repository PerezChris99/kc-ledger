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

[Icons]
Name: "{group}\KC Ledger"; Filename: "{app}\KC Ledger.exe"
Name: "{autodesktop}\KC Ledger"; Filename: "{app}\KC Ledger.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\KC Ledger.exe"; Description: "Launch KC Ledger"; Flags: nowait postinstall skipifsilent

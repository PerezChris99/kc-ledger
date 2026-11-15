; KC Ledger installer: VERSION is generated from the canonical repository VERSION file.
#include "version.iss"
#define MyAppName "KC Ledger"
#define MyAppVersion LedgerVersion

[Setup]
AppId={{71130585-D271-4147-86AD-0AA204FC73CE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\KC Ledger
DefaultGroupName=KC Ledger
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\KC Ledger.exe
OutputDir=..\installer-output
OutputBaseFilename=KCLedger-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
ArchitecturesAllowed=x64
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

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
var
  Upgrading: Boolean;

function WebView2Installed(): Boolean;
var Ver: String;
begin
  Result :=
    (RegQueryStringValue(HKCU,
      'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Ver) and (Ver <> '') and (Ver <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM,
      'Software\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
      'pv', Ver) and (Ver <> '') and (Ver <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer; ProgramExe: String;
begin
  Result := '';
  Upgrading := False;
  ProgramExe := ExpandConstant('{app}\KC Ledger.exe');
  if FileExists(ProgramExe) then begin
    Upgrading := True;
    if (not Exec(ProgramExe, '--prepare-upgrade', '', SW_HIDE, ewWaitUntilTerminated, Code)) or
       (Code <> 0) then begin
      Result := 'Database/binary safety backup failed. Installer refused to overwrite old files.';
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Code, RestoreCode: Integer; OldFiles, CopyCmd, ProgramExe: String;
begin
  if (CurStep = ssPostInstall) and Upgrading then begin
    ProgramExe := ExpandConstant('{app}\KC Ledger.exe');
    if (not Exec(ProgramExe, '--post-upgrade-check', '', SW_HIDE,
                 ewWaitUntilTerminated, Code)) or (Code <> 0) then begin
      Exec(ProgramExe, '--restore-upgrade', '', SW_HIDE, ewWaitUntilTerminated, RestoreCode);
      OldFiles := ExpandConstant('{localappdata}\KCLedger\rollback\previous-program');
      if not DirExists(OldFiles) then begin
        RaiseException('Update aborted: old version preserved elsewhere; check update log.');
      end;
      CopyCmd := '/MIR "' + OldFiles + '" "' + ExpandConstant('{app}') + '"';
      if (not Exec(ExpandConstant('{sys}\robocopy.exe'), CopyCmd, '', SW_HIDE,
          ewWaitUntilTerminated, RestoreCode)) or (RestoreCode > 7) then begin
        RaiseException('Update failed. Old binaries remain at ' + OldFiles);
      end;
      RaiseException('Update failed. Previous files were restored; verify database recovery at ' +
        ExpandConstant('{localappdata}\KCLedger\logs\update.log'));
    end;
  end;
end;

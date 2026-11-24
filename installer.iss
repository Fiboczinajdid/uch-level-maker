; Inno Setup: installs for the current user (no admin rights) and puts an icon on the desktop
[Setup]
AppId={{6C1B0B5E-2C0B-4B52-9E0B-6E6A5B0C7D41}
AppName=UCH Level Maker
AppVersion={#Version}
AppPublisher=Fiboczinajdid
AppPublisherURL=https://github.com/Fiboczinajdid/uch-level-maker
DefaultDirName={autopf}\UCH Level Maker
PrivilegesRequired=lowest
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\UCH Level Maker.exe
OutputDir=dist
OutputBaseFilename=UCH-Level-Maker-Setup
SolidCompression=yes

[Files]
Source: "dist\UCH Level Maker\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\UCH Level Maker"; Filename: "{app}\UCH Level Maker.exe"
Name: "{autodesktop}\UCH Level Maker"; Filename: "{app}\UCH Level Maker.exe"

[Run]
Filename: "{app}\UCH Level Maker.exe"; Description: "Start UCH Level Maker"; Flags: nowait postinstall skipifsilent

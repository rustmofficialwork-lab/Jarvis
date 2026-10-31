[Setup]
AppId={{7C1D7B52-6C19-4D64-9B25-6F9A6F3E8A11}
AppName=JARVIS Desktop
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
AppVersion={#MyAppVersion}
AppPublisher=JARVIS
DefaultDirName={autopf}\JARVIS Desktop
DefaultGroupName=JARVIS Desktop
OutputDir={#SourcePath}\..\dist-installer
OutputBaseFilename=JARVIS-Setup-x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile=
UninstallDisplayIcon={app}\JARVIS.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\JARVIS.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\JARVIS Desktop"; Filename: "{app}\JARVIS.exe"
Name: "{autodesktop}\JARVIS Desktop"; Filename: "{app}\JARVIS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JARVIS.exe"; Description: "Launch JARVIS Desktop"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\JARVIS.exe"; Parameters: "--cleanup-uninstall"; Flags: runhidden waituntilterminated skipifdoesntexist

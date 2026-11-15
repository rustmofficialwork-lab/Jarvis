[Setup]
AppId={{7C1D7B52-6C19-4D64-9B25-6F9A6F3E8A11}
AppName=JARVIS Desktop
AppMutex=JARVIS.Desktop.Singleton
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif
AppVersion={#MyAppVersion}
AppPublisher=JARVIS
; Per-user installation matches PrivilegesRequired=lowest and avoids Program Files elevation failures.
DefaultDirName={localappdata}\Programs\JARVIS Desktop
DefaultGroupName=JARVIS Desktop
OutputDir={#SourcePath}\..\dist-installer
OutputBaseFilename=JARVIS-Setup-x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\JARVIS.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "offlineai"; Description: "Install offline AI now (Ollama + Llama 3.2 3B; approximately 2 GB download)"; GroupDescription: "Optional AI setup:"

[Files]
Source: "..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\setup_offline_ai.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\JARVIS Desktop"; Filename: "{app}\JARVIS.exe"
Name: "{autodesktop}\JARVIS Desktop"; Filename: "{app}\JARVIS.exe"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\setup_offline_ai.ps1"""; Description: "Set up offline AI (downloads approximately 2 GB)"; Tasks: offlineai; Flags: postinstall waituntilterminated skipifsilent
Filename: "{app}\JARVIS.exe"; Description: "Launch JARVIS Desktop"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\JARVIS.exe"; Parameters: "--cleanup-uninstall"; RunOnceId: "CleanupReminderTasks"; Flags: runhidden waituntilterminated skipifdoesntexist

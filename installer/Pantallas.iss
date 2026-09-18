#ifndef AppVersion
  #define AppVersion "0.8.0"
#endif

[Setup]
AppId={{A7C98BD0-95F5-4A18-B053-1AFA52A6388E}
AppName=Pantallas
AppVersion={#AppVersion}
AppPublisher=Yakoderaa
AppPublisherURL=https://github.com/Yakoderaa/Pantallas
AppSupportURL=https://github.com/Yakoderaa/Pantallas/issues
AppUpdatesURL=https://github.com/Yakoderaa/Pantallas/releases
DefaultDirName={localappdata}\Programs\Pantallas
DefaultGroupName=Pantallas
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\installer_output
OutputBaseFilename=PantallasSetup
SetupIconFile=..\assets\generated\pantallas.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\Pantallas.exe
VersionInfoCompany=Yakoderaa
VersionInfoDescription=Control de monitores y ventanas para Windows
VersionInfoProductName=Pantallas
VersionInfoVersion={#AppVersion}

[Files]
Source: "..\dist\Pantallas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Pantallas"; Filename: "{app}\Pantallas.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Pantallas"; Filename: "{app}\Pantallas.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Run]
Filename: "{app}\Pantallas.exe"; WorkingDir: "{app}"; Flags: nowait runasoriginaluser

#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{A7C98BD0-95F5-4A18-B053-1AFA52A6388E}
AppName=Pantallas
AppVersion={#AppVersion}
AppPublisher=Yakoderaa
DefaultDirName={localappdata}\Programs\Pantallas
DefaultGroupName=Pantallas
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\installer_output
OutputBaseFilename=PantallasSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\Pantallas.exe

[Files]
Source: "..\dist\Pantallas.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Pantallas"; Filename: "{app}\Pantallas.exe"
Name: "{userdesktop}\Pantallas"; Filename: "{app}\Pantallas.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Run]
Filename: "{app}\Pantallas.exe"; WorkingDir: "{app}"; Flags: nowait runasoriginaluser

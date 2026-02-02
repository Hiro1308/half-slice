#define MyAppName "Half-Slice"
#define MyAppVersion "0.9"
#define MyAppExeName "main.exe"

[Setup]
AppId={{B5D3D3A9-6A8D-4A1E-9C8B-9F3B8B3B2A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

OutputDir=.
OutputBaseFilename=HalfSliceInstaller
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\assets\icon.ico

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=lowest

; Si tu build es 64-bit, dejalo. Si es 32-bit, borrá estas 2 líneas.
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "Crear ícono en el Escritorio"; GroupDescription: "Accesos:"; Flags: unchecked

[Files]
; ✅ COPIA TODO EL ONEDIR (incluye _internal y python313.dll)
Source: "dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; tus recursos
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "yt-dlp.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent
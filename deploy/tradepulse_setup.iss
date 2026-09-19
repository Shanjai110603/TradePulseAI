; ==============================================================================
; TradePulse Pro — Official Windows Inno Setup Installer Script
; Produces a complete standalone Windows setup wizard (TradePulse-Setup-v2.0.0.exe)
; Modeled after AutoSignal-Setup-6.1.8.exe
; ==============================================================================

#define MyAppName "TradePulse Pro"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "TradePulse Technologies"
#define MyAppURL "https://tradepulse.io"
#define MyAppExeName "TradePulse.exe"

[Setup]
; Unique application GUID for Windows Add/Remove Programs registry
AppId={{9C8E74B1-2D8F-4A9B-B1A7-8E54F3B92E10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\TradePulse
DisableProgramGroupPage=yes
; Lowest privileges allows standard users to install without needing Admin UAC password
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=TradePulse-Setup-v2.0.0
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "Create a Quick Launch shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Distribute all files compiled by PyInstaller in dist\TradePulse\*
Source: "..\dist\TradePulse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

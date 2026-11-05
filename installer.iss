#define MyAppName "Renomeador de Folhas (RDF)"
#ifndef MyAppVersion
  #define MyAppVersion "2.1.0"
#endif
#define MyAppPublisher "RENAPSI"
#define MyAppExeName "RDF.exe"

[Setup]
AppId={{D3BE12D9-84A1-4C81-A2B7-73FB83D45C10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\RDF
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=RDF_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=TERMS\TERMS_OF_USE.txt
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
#if FileExists("ICON\\icone.ico")
SetupIconFile=ICON\icone.ico
#endif

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "dist\RDF.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "TERMS\TERMS_OF_USE.txt"; DestDir: "{app}\TERMOS"; DestName: "Termos de Uso.txt"; Flags: ignoreversion
Source: "TERMS\TERMS_MAINTENANCE_GUIDE.txt"; DestDir: "{app}\TERMOS"; DestName: "Orientacoes para Alteracao dos Termos.txt"; Flags: ignoreversion
#if FileExists("DOCUMENTATION\DELIVERY_GUIDE.md")
Source: "DOCUMENTATION\DELIVERY_GUIDE.md"; DestDir: "{app}\DOCUMENTACAO"; DestName: "Guia de Entrega.md"; Flags: ignoreversion
#endif

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

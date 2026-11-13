; Installatieprogramma voor Windows. Gebouwd met Inno Setup (zie .github/workflows/bouw.yml).
; Zonder beheerdersrechten: alles komt in de map van de gebruiker. Het programma start vanzelf bij het aanmelden.

#ifndef Versie
  #define Versie "1.0.0"
#endif

[Setup]
AppId={{5D3C9B52-6B0E-4C45-9E2B-1B7E1A0C51F7}
AppName=Soigneur kaartlezer
AppVersion={#Versie}
AppPublisher=Xochi
AppPublisherURL=https://mijnsoigneur.be
DefaultDirName={localappdata}\Programs\Soigneur kaartlezer
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Soigneur-kaartlezer-windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=Soigneur kaartlezer
CloseApplications=no

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Files]
Source: "..\dist\Soigneur-kaartlezer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Automatisch starten bij het aanmelden
Name: "{userstartup}\Soigneur kaartlezer"; Filename: "{app}\Soigneur-kaartlezer.exe"

[Run]
; Meteen starten, zonder venster
Filename: "{app}\Soigneur-kaartlezer.exe"; Flags: nowait runhidden

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Soigneur-kaartlezer.exe"; Flags: runhidden; RunOnceId: "StopKaartlezer"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  // Een draaiende oudere versie stoppen, zodat de nieuwe de bestanden kan vervangen.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Soigneur-kaartlezer.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;

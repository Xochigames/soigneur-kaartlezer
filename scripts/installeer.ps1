# Soigneur-kaartlezer voor Windows, voor wie liever een commando gebruikt dan het installatieprogramma.
# Het gewone installatieprogramma staat op https://mijnsoigneur.be/app/kaartlezer.
#
# Installeren (in PowerShell):  irm https://raw.githubusercontent.com/Xochigames/soigneur-kaartlezer/main/scripts/installeer.ps1 | iex
# Verwijderen:                  $env:SOIGNEUR_ACTIE='verwijder'; irm https://raw.githubusercontent.com/Xochigames/soigneur-kaartlezer/main/scripts/installeer.ps1 | iex
#
# Wat dit doet, in het kort:
#   1. zoekt Python 3.9 of nieuwer (staat er geen op de pc, dan wordt Python voor jouw account geinstalleerd);
#   2. maakt een eigen map met een eigen Python-omgeving: %LOCALAPPDATA%\Soigneur\kaartlezer;
#   3. installeert daarin pyscard (het pakket dat de kaartlezer aanspreekt);
#   4. haalt het kaartlezerprogramma op van GitHub (de nieuwste versie);
#   5. zet een snelkoppeling in de map Opstarten, zodat het automatisch start bij het aanmelden, en start het meteen.
# Er zijn geen beheerdersrechten nodig. Alles blijft in je eigen gebruikersmap.
#
# Instellingen voor tests: SOIGNEUR_BRON, SOIGNEUR_ORIGINS, SOIGNEUR_KAARTLEZER_DIR, SOIGNEUR_ZONDER_AUTOSTART=1

function Install-SoigneurKaartlezer {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

    $Bron = if ($env:SOIGNEUR_BRON) { $env:SOIGNEUR_BRON } else { 'https://github.com/Xochigames/soigneur-kaartlezer/releases/latest/download' }
    $Origin = if ($env:SOIGNEUR_ORIGINS) { ($env:SOIGNEUR_ORIGINS -split ',')[0].Trim() } else { 'https://mijnsoigneur.be' }
    $Dir = if ($env:SOIGNEUR_KAARTLEZER_DIR) { $env:SOIGNEUR_KAARTLEZER_DIR } else { Join-Path $env:LOCALAPPDATA 'Soigneur\kaartlezer' }
    $Port = if ($env:SOIGNEUR_EID_PORT) { $env:SOIGNEUR_EID_PORT } else { '47011' }
    $Snelkoppeling = Join-Path ([Environment]::GetFolderPath('Startup')) 'Soigneur kaartlezer.lnk'
    $Script = Join-Path $Dir 'soigneur_eid.py'
    $Pythonw = Join-Path $Dir 'venv\Scripts\pythonw.exe'
    $VenvPython = Join-Path $Dir 'venv\Scripts\python.exe'

    function Stop-Kaartlezer {
        # Een draaiende kaartlezer stoppen, zodat een nieuwe versie het overneemt.
        try {
            Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.CommandLine -and $_.CommandLine -like '*soigneur_eid.py*' } |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        } catch { }
    }

    function Find-Python {
        $kandidaten = @()
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            try { $p = (& py -3 -c "import sys; print(sys.executable)") 2>$null; if ($p) { $kandidaten += "$p".Trim() } } catch { }
        }
        foreach ($naam in 'python', 'python3') {
            $c = Get-Command $naam -ErrorAction SilentlyContinue
            # De Python-snelkoppeling van de Microsoft Store (WindowsApps) is geen echte Python.
            if ($c -and $c.Source -notlike '*WindowsApps*') { $kandidaten += $c.Source }
        }
        $mappen = @("$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe", "$env:ProgramFiles\Python3*\python.exe")
        foreach ($m in $mappen) {
            Get-ChildItem $m -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $kandidaten += $_.FullName }
        }
        foreach ($k in $kandidaten) {
            try {
                & $k -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
                if ($LASTEXITCODE -eq 0) { return $k }
            } catch { }
        }
        return $null
    }

    try {
        if ($env:SOIGNEUR_ACTIE -eq 'verwijder') {
            Write-Host 'Soigneur-kaartlezer verwijderen...'
            Stop-Kaartlezer
            if (Test-Path $Snelkoppeling) { Remove-Item $Snelkoppeling -Force }
            if (Test-Path $Dir) { Remove-Item $Dir -Recurse -Force }
            Write-Host 'Klaar. De kaartlezer is verwijderd en start niet meer.' -ForegroundColor Green
            return
        }

        # 1. Python zoeken (3.9 of nieuwer), anders installeren voor deze gebruiker
        $python = Find-Python
        if (-not $python) {
            $winget = Get-Command winget -ErrorAction SilentlyContinue
            if ($winget) {
                Write-Host 'Python wordt geinstalleerd (enkel voor jouw account)...'
                & winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
                $python = Find-Python
            }
        }
        if (-not $python) {
            throw "er is geen Python 3.9 of nieuwer op deze pc. Installeer Python via https://www.python.org/downloads/windows/ (vink 'Add python.exe to PATH' aan) en voer dit commando daarna opnieuw uit."
        }
        Write-Host "Python gevonden: $python"

        # 2 en 3. Eigen omgeving met pyscard
        New-Item -ItemType Directory -Force -Path $Dir | Out-Null
        Stop-Kaartlezer
        if (-not (Test-Path $VenvPython)) {
            Write-Host 'Een eigen Python-omgeving maken...'
            & $python -m venv (Join-Path $Dir 'venv')
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { throw 'de Python-omgeving kon niet gemaakt worden.' }
        }
        Write-Host 'pyscard installeren (om de kaartlezer aan te spreken)...'
        $oud = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $VenvPython -m pip install --quiet --upgrade pip 2>&1 | Out-Null
        & $VenvPython -m pip install --quiet --upgrade pyscard 2>&1 | Out-Null
        $pipFout = $LASTEXITCODE
        $ErrorActionPreference = $oud
        if ($pipFout -ne 0) { throw 'pyscard kon niet geinstalleerd worden. Controleer je internetverbinding en probeer opnieuw.' }

        # 4. Het kaartlezerprogramma ophalen
        Write-Host 'Het kaartlezerprogramma ophalen...'
        Invoke-WebRequest -Uri "$Bron/soigneur_eid.py" -OutFile "$Script.nieuw" -UseBasicParsing
        Move-Item "$Script.nieuw" $Script -Force

        # 5. Automatisch starten (map Opstarten) en nu starten
        if ($env:SOIGNEUR_ZONDER_AUTOSTART -ne '1') {
            $shell = New-Object -ComObject WScript.Shell
            $lnk = $shell.CreateShortcut($Snelkoppeling)
            $lnk.TargetPath = $Pythonw
            $lnk.Arguments = '"' + $Script + '"'
            $lnk.WorkingDirectory = $Dir
            $lnk.WindowStyle = 7
            $lnk.Description = 'Soigneur-kaartlezer (leest de identiteitskaart voor Soigneur)'
            $lnk.Save()
        }
        Start-Process -FilePath $Pythonw -ArgumentList ('"' + $Script + '"') -WorkingDirectory $Dir -WindowStyle Hidden

        # Controle: antwoordt de kaartlezer?
        for ($i = 0; $i -lt 10; $i++) {
            try {
                $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/status" -Headers @{ Origin = $Origin } -UseBasicParsing
                if ($r.ok) {
                    Write-Host ''
                    Write-Host 'Klaar. De Soigneur-kaartlezer draait en start voortaan vanzelf bij het aanmelden op deze pc.' -ForegroundColor Green
                    Write-Host 'Steek de identiteitskaart in de lezer en klik in Soigneur op "Identiteitskaart lezen".'
                    Write-Host 'De eerste keer vraagt Chrome of Edge of Soigneur apparaten op je netwerk mag gebruiken. Kies Toestaan.'
                    return
                }
            } catch { }
            Start-Sleep -Seconds 1
        }
        throw 'de kaartlezer is geinstalleerd maar antwoordt niet. Start de pc opnieuw op en probeer het nog eens.'
    }
    catch {
        Write-Host ''
        Write-Host ('Dit lukte niet: ' + $_.Exception.Message) -ForegroundColor Red
    }
    finally {
        # De keuze "verwijder" mag niet in dit venster blijven hangen, anders verwijdert een volgende installatie weer alles.
        Remove-Item Env:\SOIGNEUR_ACTIE -ErrorAction SilentlyContinue
    }
}

Install-SoigneurKaartlezer

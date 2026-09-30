# Scrape quotidien des groupes Facebook immo Bangkok.
#
# Rapatrié de C:\agentic\agents\agent2_scraper le 2026-09-13 : le script y
# vivait hors de tout dépôt, la doc Lowi l'ignorait, et la tâche Windows
# rendait 0x1 chaque nuit alors que son log disait « ok » — le code retour
# était celui du DERNIER taskkill (aucun Chrome à tuer → 128), pas celui du
# scrape. Ici le code retour est celui de node facebook/agent.js.
#
# Profil Chrome dédié (ChromeAutomationProfile, à connecter à Facebook une
# fois à la main), pas de WhatsApp, pas d'analyse Ollama (FB_SKIP_ANALYSIS=1 :
# collecte brute, l'extraction structurée se fait en aval — décision du
# 2026-09-12). Enregistré par ops\install-facebook-task.ps1.
#
# Sorties : scraper\output\social\immo_YYYY-MM-DD.json (données, gitignoré),
#           ops\logs\facebook\ (journaux), scraper\social\logs\sonde-immo.json.

$socialDir  = $PSScriptRoot
$root       = Split-Path -Parent (Split-Path -Parent $socialDir)
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$workProfile = "$env:USERPROFILE\ChromeAutomationProfile"
$logDir  = Join-Path $root "ops\logs\facebook"
$logFile = Join-Path $logDir "immo-$(Get-Date -Format 'yyyy-MM-dd_HHmm').log"

New-Item -ItemType Directory -Force $logDir | Out-Null
New-Item -ItemType Directory -Force (Join-Path $root "scraper\output\social") | Out-Null

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Close-AllChrome {
    # Ferme TOUT Chrome, y compris celui de l'utilisateur : le port CDP 9222
    # doit être libre et un seul profil ouvert à la fois. C'est pour ça que la
    # tâche tourne à 01:00.
    taskkill /F /IM chrome.exe /T 2>$null | Out-Null
    Start-Sleep -Seconds 2
}

Add-Type -Name Power -Namespace Win32 -MemberDefinition '
[DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'
$ES_CONTINUOUS = [uint32]"0x80000000"
$ES_SYSTEM_REQUIRED = [uint32]"0x00000001"
[Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED) | Out-Null

Write-Log "=== Scrape immo Facebook — démarrage ($socialDir) ==="
$codeFinal = 1   # tout chemin qui n'atteint pas le scrape est un échec

try {
    if (-not (Test-Path (Join-Path $socialDir "node_modules"))) {
        throw "node_modules absent - lancer npm install dans $socialDir"
    }
    Close-AllChrome

    if (-not (Test-Path $workProfile)) {
        throw "Profil Chrome d'automatisation introuvable ($workProfile) — login Facebook manuel requis avant le 1er run"
    }

    Write-Log "Lancement Chrome (profil d'automatisation)..."
    $chromeArgs = "--remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir=`"$workProfile`" --no-first-run --no-default-browser-check"
    Start-Process $chromePath -ArgumentList $chromeArgs -PassThru `
        -RedirectStandardError (Join-Path $logDir "chrome-err-last.log") | Out-Null

    Start-Sleep -Seconds 5
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 3
        try {
            Invoke-WebRequest -Uri "http://127.0.0.1:9222/json" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop | Out-Null
            $ready = $true
            break
        } catch { Write-Log "Attente Chrome... ($i/20)" }
    }
    if (-not $ready) { throw "Chrome n'a pas démarré sur le port 9222" }
    Write-Log "Chrome prêt"

    Set-Location $socialDir
    $env:FB_GROUPS_FILE = "./immo-groups.json"
    $env:FB_SOURCE = "immo"
    $env:FB_SKIP_ANALYSIS = "1"
    $env:FB_RICH_CONTENT = "1"
    $env:FB_DAYS_BACK = "7"
    # Profondeur de défilement par groupe. 15 tours (défaut) = ~12 h de posts,
    # mesuré le 2026-09-30, pour une collecte quotidienne : environ la moitié
    # des posts n'était jamais vue (déduit, si le rythme de publication est
    # régulier). 32 tours visent ~24 h + marge. Le coût : une collecte ~2×
    # plus longue (6,5 → ~13 min estimés) et deux fois plus de défilement sur
    # le compte. Le défilement s'arrête de toute façon dès 2 tours sans post
    # nouveau. Retour arrière : supprimer cette ligne (on revient à 15).
    # À recalibrer sur `plus_ancien` et `arret` dans logs/sonde-immo.json.
    $env:FB_MAX_SCROLL = "32"

    Write-Log "Lancement du scrape immo..."
    $fb = Start-Process "node" -ArgumentList "facebook/agent.js" -WorkingDirectory $socialDir -PassThru `
        -RedirectStandardOutput (Join-Path $logDir "immo-last.log") `
        -RedirectStandardError (Join-Path $logDir "immo-err.log") -NoNewWindow
    if (-not $fb.WaitForExit(1800000)) {   # 30 min max
        Write-Log "ERREUR : scrape au-delà de 30 min — arrêté"
        $fb.Kill()
    } else {
        $codeFinal = $fb.ExitCode
    }
    Write-Log "Scrape immo exit code : $($fb.ExitCode)"
}
catch {
    Write-Log "ERREUR : $($_.Exception.Message)"
}
finally {
    Close-AllChrome
    Write-Log "Chrome fermé"
    Write-Log "=== Scrape immo Facebook — terminé (code $codeFinal) ==="
    [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
}
exit $codeFinal

#Requires -Version 7.0
<#
.SYNOPSIS
    Widget de bureau : prochaines échéances des tâches Windows, des routines
    Claude et des agents Lowi (T0/T1 qwen).

.DESCRIPTION
    Fenêtre WPF sans bordure, posée sur le bureau. Deux ancrages, réglés par
    "ancrage" dans config.json :

      · "arriere_plan" (défaut) — fenêtre de premier niveau maintenue au fond de
        la pile Z, sans activation ni entrée dans la barre des tâches. Elle
        reste derrière toutes les applications et réapparaît dès que le bureau
        est visible, tout en restant CLIQUABLE (clic droit = menu), et elle
        survit à un redémarrage d'Explorer.

      · "bureau" — vraie fenêtre-fille du WorkerW d'Explorer, peinte dans le
        fond d'écran, derrière les icônes. Plus intégré, deux contreparties
        réelles : la couche des icônes couvre tout le bureau et intercepte la
        souris (le widget n'y est plus cliquable — le piloter par config.json),
        et un redémarrage d'Explorer détruit le parent donc la fenêtre, d'où la
        relance par garde.vbs.

    SOBRIÉTÉ — le widget tourne en permanence, il est écrit pour peser le moins
    possible :
      · aucune dépendance à System.Windows.Forms ni System.Drawing (le menu est
        un ContextMenu WPF, pas une icône de zone de notification) ;
      · la collecte s'exécute dans un processus court, séparé, qui écrit
        etat.json — rien de lourd ne reste chargé entre deux relevés ;
      · l'interface n'est reconstruite que si etat.json a changé ;
      · le jeu de pages est rendu au système après chaque reconstruction.

    Rafraîchissement : au démarrage, toutes les N minutes, et à chaque sortie de
    veille ou déverrouillage (SystemEvents lève un drapeau, la minuterie le
    relève — pas de rappel inter-thread, qui échouerait faute de Runspace).

    Attention en relisant ce fichier : PowerShell ignore la casse des noms de
    variables. $C (palette) et un $c de boucle sont la MÊME variable.
#>
[CmdletBinding()]
param(
    [switch]$Detache   # démarre en mode déplacement (fenêtre libre, au-dessus)
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$ICI     = Split-Path -Parent $MyInvocation.MyCommand.Path
$FIC_CFG = Join-Path $ICI 'config.json'
$ETAT    = Join-Path $ICI 'etat.json'
$JOURNAL = Join-Path $ICI 'widget.log'
$ARRET   = Join-Path $ICI '.arret'
Remove-Item $ARRET -ErrorAction SilentlyContinue

$FR = [System.Globalization.CultureInfo]::GetCultureInfo('fr-FR')

function Trace {
    param([string]$M)
    try {
        # Journal borné : il tourne des mois sans surveillance, il ne doit pas
        # grossir indéfiniment.
        if ((Test-Path $JOURNAL) -and (Get-Item $JOURNAL).Length -gt 200KB) {
            Remove-Item $JOURNAL -ErrorAction SilentlyContinue
        }
        "$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))  $M" | Add-Content $JOURNAL -Encoding utf8
    } catch { }
}

# ───────────────────────── interop Windows ─────────────────────────
if (-not ('Lowi.Bureau' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace Lowi {
  public static class Bureau {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }

    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string c, string w);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowEx(IntPtr p, IntPtr a, string c, string w);
    [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h, uint m, IntPtr w, IntPtr l, uint f, uint t, out IntPtr r);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern IntPtr SetParent(IntPtr child, IntPtr parent);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int i);
    [DllImport("user32.dll")] public static extern int SetWindowLong(IntPtr h, int i, int v);
    [DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr h, int a, ref int v, int s);
    [DllImport("psapi.dll")] public static extern bool EmptyWorkingSet(IntPtr h);
    [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();

    public const int GWL_EXSTYLE = -20;
    public const int WS_EX_NOACTIVATE = 0x08000000;
    public const int WS_EX_TOOLWINDOW = 0x00000080;
    public static readonly IntPtr HWND_BOTTOM = new IntPtr(1);
    public const uint SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_NOACTIVATE = 0x0010, SWP_NOZORDER = 0x0004;

    // Rend au système les pages devenues inutiles après une reconstruction de
    // l'interface. Le tas managé n'est pas réduit, seul le jeu de pages
    // résident l'est — c'est exactement ce qu'on veut pour un processus qui
    // dort 99,9 % du temps.
    public static void Degonfler() { EmptyWorkingSet(GetCurrentProcess()); }

    // Demande à Progman de matérialiser le WorkerW qui porte le fond d'écran.
    // Le message 0x052C n'est pas documenté et ses arguments ont changé selon
    // les versions de Windows : on essaie les deux formes connues.
    public static IntPtr TrouverWorkerW() {
      IntPtr progman = FindWindow("Progman", null);
      if (progman == IntPtr.Zero) return IntPtr.Zero;
      IntPtr r;
      SendMessageTimeout(progman, 0x052C, IntPtr.Zero, IntPtr.Zero, 0, 1000, out r);
      IntPtr w = Chercher();
      if (w == IntPtr.Zero) {
        SendMessageTimeout(progman, 0x052C, new IntPtr(0xD), new IntPtr(0x1), 0, 1000, out r);
        w = Chercher();
      }
      return w;
    }

    // Le WorkerW utile est le FRÈRE SUIVANT de la fenêtre qui héberge
    // SHELLDLL_DefView (la couche des icônes) : lui seul est peint sous les
    // icônes et au-dessus du fond d'écran.
    private static IntPtr Chercher() {
      IntPtr trouve = IntPtr.Zero;
      EnumWindows(delegate(IntPtr h, IntPtr l) {
        if (FindWindowEx(h, IntPtr.Zero, "SHELLDLL_DefView", null) != IntPtr.Zero) {
          IntPtr w = FindWindowEx(IntPtr.Zero, h, "WorkerW", null);
          if (w != IntPtr.Zero) trouve = w;
        }
        return true;
      }, IntPtr.Zero);
      return trouve;
    }
  }

  // Sortie de veille et déverrouillage. On ne rappelle PAS de code PowerShell
  // depuis ces événements : ils arrivent sur un thread sans Runspace, l'appel
  // échouerait. On lève un drapeau, la minuterie le relève.
  public static class Veille {
    private static volatile bool _drapeau;
    public static bool Releve() { if (_drapeau) { _drapeau = false; return true; } return false; }
    public static void Brancher() {
      Microsoft.Win32.SystemEvents.PowerModeChanged += delegate(object s, Microsoft.Win32.PowerModeChangedEventArgs e) {
        if (e.Mode == Microsoft.Win32.PowerModes.Resume) _drapeau = true;
      };
      Microsoft.Win32.SystemEvents.SessionSwitch += delegate(object s, Microsoft.Win32.SessionSwitchEventArgs e) {
        if (e.Reason == Microsoft.Win32.SessionSwitchReason.SessionUnlock ||
            e.Reason == Microsoft.Win32.SessionSwitchReason.ConsoleConnect ||
            e.Reason == Microsoft.Win32.SessionSwitchReason.SessionLogon)
          _drapeau = true;
      };
      Microsoft.Win32.SystemEvents.TimeChanged += delegate(object s, EventArgs e) { _drapeau = true; };
    }
  }
}
'@ -ReferencedAssemblies Microsoft.Win32.SystemEvents
}

# ───────────── palette : pinceaux gelés, créés une seule fois ─────────────
function Gel([string]$Hex) {
    $b = [System.Windows.Media.SolidColorBrush]::new([System.Windows.Media.ColorConverter]::ConvertFromString($Hex))
    $b.Freeze()   # partageable, non cloné à chaque usage
    $b
}
$P = @{
    or      = Gel '#C9A84C'; violet = Gel '#8E7BD0'
    texte   = Gel '#DCD7E8'; faible = Gel '#7C748F'
    ambre   = Gel '#D9A63C'; rouge  = Gel '#D46A6A'
}

# ───────────────────────────── fenêtre ─────────────────────────────
[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" ResizeMode="NoResize" ShowInTaskbar="False"
        AllowsTransparency="False" Background="#141020"
        SizeToContent="Height" Width="240" Left="0" Top="0"
        FontFamily="Segoe UI" TextOptions.TextFormattingMode="Display"
        UseLayoutRounding="True" SnapsToDevicePixels="True" Topmost="False">
  <Border BorderBrush="#26203A" BorderThickness="1" Padding="9,7,9,7">
    <StackPanel x:Name="Corps"/>
  </Border>
</Window>
'@

$W     = [Windows.Markup.XamlReader]::Load([System.Xml.XmlNodeReader]::new($xaml))
$Corps = $W.FindName('Corps')

# ─────────────────────────── configuration ───────────────────────────
function Lire-Config {
    try { [System.IO.File]::ReadAllText($FIC_CFG) | ConvertFrom-Json }
    catch { Trace "config.json illisible : $_"; $null }
}
$script:reglages = Lire-Config
if (-not $script:reglages) { throw "config.json introuvable ou invalide : $FIC_CFG" }
$script:ancrage = if ($script:reglages.ancrage) { [string]$script:reglages.ancrage } else { 'arriere_plan' }
$script:libre   = [bool]$Detache
$script:signature = ''
$W.Width   = [double]$script:reglages.largeur
$W.Opacity = if ($script:reglages.opacite) { [double]$script:reglages.opacite } else { 1.0 }

# Une seule taille réglée dans la config ; les intitulés de section et la ligne
# d'alerte s'en déduisent, pour qu'ils gardent leur rapport quoi qu'on choisisse.
function Taille { if ($script:reglages.taille_police) { [double]$script:reglages.taille_police } else { 12.5 } }

function Ecrire-Position([int]$X, [int]$Y) {
    try {
        $j = [System.IO.File]::ReadAllText($FIC_CFG) | ConvertFrom-Json
        $j.position.x = $X; $j.position.y = $Y
        [System.IO.File]::WriteAllText($FIC_CFG, ($j | ConvertTo-Json -Depth 6))
        $script:reglages = $j
        Trace "position enregistree : $X,$Y"
    } catch { Trace "ecriture position : $_" }
}

# ──────────────────────────── mise en page ────────────────────────────
function Format-Echeance {
    param($T)
    if (-not $T) { return '—' }
    $t = if ($T -is [datetime]) { $T }
         else { [datetime]::Parse([string]$T, [cultureinfo]::InvariantCulture,
                                  [System.Globalization.DateTimeStyles]::RoundtripKind) }
    $d = $t - (Get-Date)
    if ($d.TotalSeconds -lt 0)       { return 'imminent' }
    if ($d.TotalMinutes -lt 90)      { return "{0} min" -f [int]$d.TotalMinutes }
    if ($t.Date -eq (Get-Date).Date) { return $t.ToString('HH:mm', $FR) }
    if ($t.Date -eq (Get-Date).Date.AddDays(1)) { return $t.ToString("'dem.' HH:mm", $FR) }
    if ($d.TotalDays -lt 6)          { return $t.ToString('ddd HH:mm', $FR) }
    return $t.ToString('dd/MM HH:mm', $FR)
}

function Titre([string]$Texte) {
    $t = [Windows.Controls.TextBlock]::new()
    $t.Text = $Texte; $t.FontSize = (Taille) - 2.5; $t.Foreground = $P.violet
    $t.Margin = if ($Corps.Children.Count) { '0,7,0,2' } else { '0,0,0,2' }
    $Corps.Children.Add($t) | Out-Null
}

function Ligne {
    param([string]$Nom, [string]$Valeur, $Couleur = $P.texte, [string]$Info)
    $g = [Windows.Controls.Grid]::new()
    # Ni $c ni $w comme variables locales ici : ce sont $C et $W à la casse près.
    $col1 = [Windows.Controls.ColumnDefinition]::new()
    $col2 = [Windows.Controls.ColumnDefinition]::new(); $col2.Width = 'Auto'
    $g.ColumnDefinitions.Add($col1); $g.ColumnDefinitions.Add($col2)

    $n = [Windows.Controls.TextBlock]::new()
    $n.Text = $Nom; $n.FontSize = Taille; $n.Foreground = $P.texte
    $n.TextTrimming = 'CharacterEllipsis'
    if ($Info) { $n.ToolTip = $Info }
    $g.Children.Add($n) | Out-Null

    $v = [Windows.Controls.TextBlock]::new()
    $v.Text = $Valeur; $v.FontSize = Taille; $v.Foreground = $Couleur; $v.Margin = '8,0,0,0'
    [Windows.Controls.Grid]::SetColumn($v, 1)
    $g.Children.Add($v) | Out-Null

    $Corps.Children.Add($g) | Out-Null
}

function Construire {
    param($E)
    $Corps.Children.Clear()
    # Largeur et opacité relues ici aussi : sans ça, les modifier dans
    # config.json n'aurait d'effet qu'au redémarrage, contrairement au reste.
    $W.Width   = [double]$script:reglages.largeur
    $W.Opacity = if ($script:reglages.opacite) { [double]$script:reglages.opacite } else { 1.0 }

    if (-not $E) { Ligne 'en attente de la collecte' '' $P.faible; return }

    # Le préfixe commun se répète sur chaque ligne sans rien apprendre : on
    # l'ôte de l'affichage, le nom complet reste dans l'infobulle.
    $prefixe = [string]$script:reglages.prefixe_a_retirer

    if ($E.taches.Count) {
        Titre 'WINDOWS'
        foreach ($t in $E.taches) {
            $court = if ($prefixe -and $t.nom.StartsWith($prefixe)) { $t.nom.Substring($prefixe.Length) } else { $t.nom }
            if ($t.desactivee) { Ligne $court 'off' $P.faible $t.nom; continue }
            $val  = if ($t.encours) { 'en cours' } else { Format-Echeance $t.prochain }
            $coul = if ($t.echec) { $P.rouge } else { $P.texte }
            $info = "$($t.nom) — dernier : $(if ($t.dernier) { ([datetime]$t.dernier).ToString('dd/MM HH:mm', $FR) } else { 'jamais' })"
            if ($t.echec) { $info += " (code $($t.resultat))" }
            Ligne $court $val $coul $info
        }
    }

    $actives = @($E.claude | Where-Object { $_.actif })
    if ($actives.Count) {
        Titre 'CLAUDE'
        foreach ($r in $actives) { Ligne $r.nom (Format-Echeance $r.prochain) $P.texte $r.id }
    }

    if ($E.agents.Count) {
        Titre 'AGENTS'
        $prochain = @($E.agents | Where-Object { $_.prochain } |
                      Sort-Object { [datetime]$_.prochain } | Select-Object -First 1).prochain
        Ligne 'cycle' (Format-Echeance $prochain) $P.or `
              'Les agents dus partent au prochain declenchement de la tache orchestrateur.'

        $rates = @($E.agents | Where-Object { $_.statut -and $_.statut -notin @('ok', 'skipped') })
        if ($script:reglages.agents_detail) {
            foreach ($a in $E.agents) {
                $mauvais = $a.statut -and $a.statut -notin @('ok', 'skipped')
                $coul = if ($mauvais) { $P.rouge } elseif ($a.du) { $P.ambre } else { $P.faible }
                $val  = if ($mauvais) { $a.statut } else { Format-Echeance $a.prochain }
                Ligne $a.nom $val $coul "$($a.tier) — cadence $($a.every_days) j"
            }
        } else {
            $dus = @($E.agents | Where-Object { $_.du }).Count
            if ($dus)         { Ligne 'dus au cycle' "$dus/$($E.agents.Count)" $P.ambre }
            foreach ($a in $rates) { Ligne $a.nom $a.statut $P.rouge }
        }
    }

    # Pied réduit à ce qui mérite le coup d'œil : rien à signaler, rien affiché.
    $alertes = @()
    if ($null -ne $E.ollama.ok -and -not $E.ollama.ok) { $alertes += "qwen $($E.ollama.message)" }
    if ($E.escalades -gt 0)      { $alertes += "$($E.escalades) escalade(s)" }
    if ($E.constats_hauts -gt 0) { $alertes += "$($E.constats_hauts) constat(s) haut(s)" }
    if ($E.erreurs.Count)        { $alertes += "$($E.erreurs.Count) erreur(s) de collecte" }
    if ($alertes.Count) {
        $a = [Windows.Controls.TextBlock]::new()
        $a.Text = $alertes -join ' · '
        $a.FontSize = (Taille) - 2.5; $a.Foreground = $P.ambre; $a.Margin = '0,6,0,0'
        $a.TextWrapping = 'Wrap'
        if ($E.erreurs.Count) { $a.ToolTip = ($E.erreurs -join "`n") }
        $Corps.Children.Add($a) | Out-Null
    }
}

# ─────────────────────────── collecte ───────────────────────────
$script:proc = $null
function Lancer-Collecte {
    if ($script:proc -and -not $script:proc.HasExited) { return }
    try {
        $script:proc = Start-Process -FilePath (Get-Process -Id $PID).Path `
            -ArgumentList '-NoProfile', '-NonInteractive', '-File',
                          (Join-Path $ICI 'collecte.ps1'), '-Sortie', $ETAT `
            -WindowStyle Hidden -PassThru
    } catch { Trace "lancement collecte : $_"; $script:proc = $null }
}

function Charger-Etat {
    param([switch]$Force)
    if (-not (Test-Path $ETAT)) { return }
    try {
        $brut = [System.IO.File]::ReadAllText($ETAT)
        # Reconstruire pour rien coûte des objets WPF : on ne le fait que si le
        # contenu a bougé (ou si les libellés relatifs doivent être réécrits).
        if (-not $Force -and $brut -eq $script:signature) { return }
        $script:signature = $brut
        Construire ($brut | ConvertFrom-Json)
        [Lowi.Bureau]::Degonfler()
    } catch { Trace "lecture etat : $_" }
}

# ─────────────────────── ancrage sur le bureau ───────────────────────
$script:hwnd = [IntPtr]::Zero
$script:dpi  = 1.0

function Placer([int]$X, [int]$Y) {
    # Rattachée au WorkerW, la fenêtre est positionnée dans le CLIENT du parent
    # et non à l'écran : sans conversion elle partirait hors champ en multi-écran.
    $parent = [Lowi.Bureau]::GetParent($script:hwnd)
    $px = $X; $py = $Y
    if ($parent -ne [IntPtr]::Zero) {
        $pt = [Lowi.Bureau+POINT]::new(); $pt.X = $X; $pt.Y = $Y
        if ([Lowi.Bureau]::ScreenToClient($parent, [ref]$pt)) { $px = $pt.X; $py = $pt.Y }
    }
    [void][Lowi.Bureau]::SetWindowPos($script:hwnd, [IntPtr]::Zero, $px, $py, 0, 0,
        ([Lowi.Bureau]::SWP_NOSIZE -bor [Lowi.Bureau]::SWP_NOZORDER -bor [Lowi.Bureau]::SWP_NOACTIVATE))
}

function Position-Voulue {
    $x = [int]$script:reglages.position.x
    $y = [int]$script:reglages.position.y
    # x négatif = distance au bord DROIT : seule façon d'avoir un défaut correct
    # sans connaître la résolution au moment d'écrire la config.
    if ($x -lt 0) {
        $zone = [System.Windows.SystemParameters]::WorkArea   # en unités WPF
        $x = [int](($zone.Right - $W.Width) * $script:dpi) + $x
    }
    return @($x, $y)
}

function AuFond {
    [void][Lowi.Bureau]::SetWindowPos($script:hwnd, [Lowi.Bureau]::HWND_BOTTOM, 0, 0, 0, 0,
        ([Lowi.Bureau]::SWP_NOMOVE -bor [Lowi.Bureau]::SWP_NOSIZE -bor [Lowi.Bureau]::SWP_NOACTIVATE))
}

function Attacher {
    if ($script:libre) { return }
    if ($script:ancrage -eq 'bureau') {
        $worker = [Lowi.Bureau]::TrouverWorkerW()
        if ($worker -ne [IntPtr]::Zero) { [void][Lowi.Bureau]::SetParent($script:hwnd, $worker) }
        else { Trace 'WorkerW introuvable — repli sur arriere_plan'; $script:ancrage = 'arriere_plan' }
    }
    if ($script:ancrage -eq 'arriere_plan') { AuFond }
    $pos = Position-Voulue
    Placer $pos[0] $pos[1]
}

function Detacher {
    [void][Lowi.Bureau]::SetParent($script:hwnd, [IntPtr]::Zero)
    $W.Topmost = $true
    $pos = Position-Voulue
    $W.Left = $pos[0] / $script:dpi
    $W.Top  = $pos[1] / $script:dpi
}

$W.Add_SourceInitialized({
    $src = [System.Windows.Interop.HwndSource]::FromVisual($W)
    $script:hwnd = $src.Handle
    $script:dpi  = $src.CompositionTarget.TransformToDevice.M11

    # Ni activation ni Alt+Tab : un widget ne vole jamais le focus.
    $ex = [Lowi.Bureau]::GetWindowLong($script:hwnd, [Lowi.Bureau]::GWL_EXSTYLE)
    [void][Lowi.Bureau]::SetWindowLong($script:hwnd, [Lowi.Bureau]::GWL_EXSTYLE,
        ($ex -bor [Lowi.Bureau]::WS_EX_NOACTIVATE -bor [Lowi.Bureau]::WS_EX_TOOLWINDOW))

    $rond = 2   # DWMWA_WINDOW_CORNER_PREFERENCE = arrondi
    [void][Lowi.Bureau]::DwmSetWindowAttribute($script:hwnd, 33, [ref]$rond, 4)

    if ($script:libre) { Detacher } else { Attacher }
})

# ──────────────────────────── menu ────────────────────────────
$menu = [Windows.Controls.ContextMenu]::new()
function Entree([string]$Texte, [scriptblock]$Action) {
    $i = [Windows.Controls.MenuItem]::new()
    $i.Header = $Texte
    $i.Add_Click($Action)
    $menu.Items.Add($i) | Out-Null
    $i
}
Entree 'Rafraîchir' { Lancer-Collecte } | Out-Null
$script:entreeDeplacer = Entree 'Déplacer' {
    $script:libre = -not $script:libre
    if ($script:libre) {
        Detacher
        $script:entreeDeplacer.Header = 'Fixer au bureau'
    } else {
        Ecrire-Position ([int]($W.Left * $script:dpi)) ([int]($W.Top * $script:dpi))
        $W.Topmost = $false
        Attacher
        $script:entreeDeplacer.Header = 'Déplacer'
    }
}
Entree 'Réglages' { Start-Process notepad.exe $FIC_CFG } | Out-Null
Entree 'Quitter'  {
    # Le drapeau .arret dit à garde.vbs que la sortie est voulue : sans lui, le
    # gardien relancerait aussitôt.
    New-Item $ARRET -ItemType File -Force | Out-Null
    $W.Close()
} | Out-Null
$W.ContextMenu = $menu

# Déplacement : seulement en mode libre, pour ne pas bouger par accident.
$W.Add_MouseLeftButtonDown({ if ($script:libre) { $W.DragMove() } })

# ──────────────────────────── minuterie ────────────────────────────
[Lowi.Veille]::Brancher()
$script:tics = 0
$periode = [int]$script:reglages.rafraichissement_minutes
if ($periode -lt 1) { $periode = 10 }
$parMinute = 4          # tics de 15 s

$minuterie = [System.Windows.Threading.DispatcherTimer]::new()
$minuterie.Interval = [TimeSpan]::FromSeconds(15)
$minuterie.Add_Tick({
    $script:tics++

    if ($script:proc -and $script:proc.HasExited) { $script:proc = $null; Charger-Etat }

    if ([Lowi.Veille]::Releve()) {
        Trace 'reveil / deverrouillage -> collecte'
        $script:reglages = (Lire-Config) ?? $script:reglages
        Lancer-Collecte
        $script:tics = 0
    }
    elseif ($script:tics % ($parMinute * $periode) -eq 0) {
        $script:reglages = (Lire-Config) ?? $script:reglages
        Lancer-Collecte
    }
    elseif ($script:tics % ($parMinute * 2) -eq 0) {
        Charger-Etat -Force      # réécrit les échéances relatives
    }

    if (-not $script:libre) {
        if ($script:ancrage -eq 'bureau') {
            # Explorer a redémarré : l'ancien WorkerW n'existe plus.
            $parent = [Lowi.Bureau]::GetParent($script:hwnd)
            if ($parent -eq [IntPtr]::Zero -or -not [Lowi.Bureau]::IsWindow($parent)) {
                Trace 'WorkerW perdu -> nouvelle accroche'; Attacher
            }
        } elseif ($script:tics % 2 -eq 0) { AuFond }
    }
})
$minuterie.Start()

$W.Add_Closed({ $minuterie.Stop() })

Trace "demarrage — ancrage=$script:ancrage"
Charger-Etat        # dernier état connu, tout de suite
Lancer-Collecte     # puis rafraîchissement
$W.Show()
[Lowi.Bureau]::Degonfler()
[System.Windows.Threading.Dispatcher]::Run()

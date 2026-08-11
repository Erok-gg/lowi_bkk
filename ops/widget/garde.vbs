' Gardien du widget Lowi.
'
' Lance widget.ps1 sans aucune fenetre (pwsh -WindowStyle Hidden laisse malgre
' tout clignoter une console : passer par wscript est le seul lancement
' vraiment silencieux) et le relance s'il meurt.
'
' La relance n'est pas un luxe : en ancrage "bureau" le widget est une
' fenetre-fille du WorkerW d'Explorer, et un redemarrage d'Explorer detruit le
' parent -- donc l'enfant. Sans gardien, le widget disparaitrait a la premiere
' explorer.exe qui plante.
'
' Sortie voulue par l'utilisateur ("Quitter" dans le menu) : le widget depose
' un fichier .arret, que ce script lit avant chaque relance.

Option Explicit

Dim sh, fso, ici, arret, cmd, debut, relances
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

ici   = fso.GetParentFolderName(WScript.ScriptFullName)
arret = ici & "\.arret"
cmd   = "pwsh.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & ici & "\widget.ps1"""

If fso.FileExists(arret) Then fso.DeleteFile arret

debut    = Timer
relances = 0

Do
    If fso.FileExists(arret) Then Exit Do

    On Error Resume Next
    sh.Run cmd, 0, True          ' 0 = fenetre cachee, True = attendre la fin
    If Err.Number <> 0 Then
        MsgBox "Widget Lowi : impossible de lancer pwsh.exe (PowerShell 7)." & vbCrLf & _
               "Installe-le, ou corrige le chemin dans garde.vbs." & vbCrLf & vbCrLf & _
               Err.Description, 48, "Widget Lowi"
        Exit Do
    End If
    On Error Goto 0

    If fso.FileExists(arret) Then Exit Do

    ' Garde-fou : un widget qui echoue au demarrage bouclerait indefiniment.
    ' Au-dela de 8 relances en 5 minutes, on abandonne et on le dit.
    relances = relances + 1
    If Timer - debut > 300 Then
        debut    = Timer
        relances = 0
    ElseIf relances > 8 Then
        MsgBox "Widget Lowi : 8 arrets en 5 minutes, gardien stoppe." & vbCrLf & _
               "Voir ops\widget\widget.log.", 48, "Widget Lowi"
        Exit Do
    End If

    WScript.Sleep 5000
Loop

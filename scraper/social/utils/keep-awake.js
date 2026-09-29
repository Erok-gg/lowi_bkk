import { spawn } from "child_process";
import chalk from "chalk";

/**
 * Empêche Windows de mettre l'écran/le système en veille pendant l'exécution.
 * Retourne une fonction release() à appeler dans le finally du script.
 * Quand release() est appelé, Windows reprend son profil d'alimentation normal.
 */
export function keepAwake() {
  const psScript = `
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class SleepGuard {
  [DllImport("kernel32.dll")]
  public static extern uint SetThreadExecutionState(uint esFlags);
}
"@
# ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001)
[SleepGuard]::SetThreadExecutionState(0x80000001) | Out-Null
while ($true) {
  [SleepGuard]::SetThreadExecutionState(0x80000001) | Out-Null
  Start-Sleep -Seconds 30
}
`;

  const proc = spawn("powershell.exe", ["-NonInteractive", "-Command", psScript], {
    stdio: "ignore",
    detached: false,
    windowsHide: true,
  });

  console.log(chalk.gray("  [veille désactivée pendant le script]"));

  return function release() {
    proc.kill("SIGTERM");
    console.log(chalk.gray("  [veille réactivée — profil d'alimentation normal]"));
  };
}

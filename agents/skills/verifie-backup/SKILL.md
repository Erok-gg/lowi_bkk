---
name: verifie-backup
description: Vérifie l'intégrité du backup local (archive/lowi-archive.db) avant de lancer un cycle de scrap, rattrape si besoin. Utiliser pour diagnostiquer un problème de sauvegarde ou comprendre pourquoi un rattrapage s'est déclenché.
---

# verifie-backup

## Mission
S'assurer qu'un point de retour en arrière valide existe AVANT que
l'extraction ne touche la base — sans resynchroniser à l'aveugle si le
précédent backup (`backup-apres-cycle`) a déjà fait le travail.

## Étage
**T0 — déterministe.** Famille `Prelude` : tourne en premier, séquentiel,
avant tout extracteur (voir `agents/orchestrator.py:run_lane`).

## Entrées
- `archive/lowi-archive.db` (le backup à vérifier)
- `agents/ledger.db` (dernier run `backup-apres-cycle`)
- Supabase (comptage `listings` pour le ratio de volume)

## Procédure
`ops/verifie-backup.py` — quatre vérifications, n'importe laquelle en échec
déclenche un rattrapage (`ops/sync_supabase_local.py`, sans `--prune`) :
1. `PRAGMA integrity_check` sur l'archive SQLite.
2. Les 7 tables attendues sont présentes, `listings` n'est pas vide.
3. `count(listings) archive / count(listings) Supabase >= 90 %`.
4. Le dernier run `backup-apres-cycle` de statut `ok` dans le ledger date de
   moins de `every_days + 1` jours (4+1 = 5 j actuellement).

## Contrat de sortie
```json
{"sqlite_ok": bool, "n_archive": int, "n_live": int, "ratio": float|null,
 "cadence_ok": bool, "rattrapage_necessaire": bool, "raisons": [str],
 "rattrapage_execute": bool, "rattrapage_code_retour": int|null}
```

## Bandes normales
`rattrapage_necessaire` = false la plupart du temps (le backup-apres-cycle du
cycle précédent a déjà fait le travail). `true` occasionnel = normal après un
cycle interrompu ou un premier démarrage — ce n'est un problème que si ça
arrive à CHAQUE cycle (signe que `backup-apres-cycle` échoue systématiquement,
pas juste que ce garde-fou fonctionne).

## Escalade
Si `rattrapage_necessaire` et `rattrapage_code_retour != 0` : le rattrapage
lui-même a échoué — deux backups d'affilée ratés. Ticket `agent_muet`-like via
le mécanisme d'alerte standard (code retour non-zero du script).

## Modes de panne connus
- Supabase injoignable au moment du check : le ratio n'est pas calculable
  (`ratio: null`), on ne bloque pas dessus — seuls l'intégrité SQLite et la
  fraîcheur du dernier `backup-apres-cycle` comptent dans ce cas.
- Un rattrapage qui se déclenche à CHAQUE cycle signale que
  `backup-apres-cycle` ne se termine jamais en `ok` (à diagnostiquer côté
  extraction, pas côté ce script).

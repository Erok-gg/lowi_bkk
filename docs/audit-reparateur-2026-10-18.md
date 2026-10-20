# Audit du réparateur `lowi-reparation-autonome` — 2026-10-18

Poste PC2 / `REMIZDABOSS`. Lecture seule (ledger, bases, tâches) ; rien appliqué.
Sources : `agents/audits/reparations-*.md` (33 rapports, gitignorés, du 2026-08-26
au 2026-10-18) et les entrées « Réparation autonome » de `docs/journal-technique.md`.

**Couverture, à lire avant les chiffres** : j'ai lu en entier ou en gros les
rapports des 08-29, 09-01, 09-09, 09-11, 10-04, 10-06 (extraits), 10-07, 10-08,
10-09, 10-16, 10-18, et fait une recherche par motifs sur les 33. Les ~20
autres n'ont été lus que par titre/journal. Le tableau est donc un **minimum
sourcé**, pas un recensement exhaustif.

## 1. Tableau des erreurs

| # | Date (audit) | Type | Ce qu'elle a cru | Ce qui était vrai | Coût | Consigne qui l'aurait évité |
|---|---|---|---|---|---|---|
| 1 | 2026-09-01 (`reparations-2026-09-01.md` §2) | A | `cycle_long` 17 h = extracteur bloqué | nuit manquée + run orphelin refermé par le cycle suivant | une enquête | vérifier PID vivant + mtime du log avant d'enquêter |
| 2 | 2026-09-09 (`…09-09.md` §1) | A | cycle « bloqué depuis 199 h » | PID Windows recyclé ; cycle de 14 h sain | alerte haute fausse (3ᵉ « c'est la mesure ») | idem |
| 3 | 2026-09-11 (`…09-11.md` §2) | A | `cycle_vide` | rattrapage isolé a réécrit le témoin | alerte haute fausse | idem |
| 4 | 2026-10-01 (journal) | A | `cycle_long` 17 h / `cycle_manquant` 41 h | cycle **suspendu** (capot, veille), pas bloqué | enquête | idem |
| 5 | 2026-10-04 (`…10-04.md` §2) | A | `cycle_manquant` 26,4 h | écart entre deux *fins* de cycle ; un cycle tournait | alerte fausse | idem |
| 6 | 2026-10-05→08 (`…10-07.md`, `…10-08.md`) | A + H | `parseur_casse` FazWaz ×3 à examiner | sitemap non régénéré par le site ; signalé 05/10 et 07/10, corrigé le 08/10 | 3 constats hauts en 5 nuits, 3 jours de retard | distinguer « reclasser une cause » (permis) de « changer un seuil » (interdit) — la règle « jamais de seuil » a retenu le correctif (`…10-06.md:260`) |
| 7 | 2026-10-09 (`…10-09.md` l.173-214) | B | — | le drapeau `--strict-mcp-config` était dans `veille-cycle.py` depuis le 04/10, absent de `social-leads` | **45 posts perdus** sur 3 cycles (01, 06, 08/10) | après un correctif, chercher les autres appelants du même motif (`claude -p`) |
| 8 | 2026-09-13 → 09-29 (journal 09-29) | B | — | mot de passe en clair diagnostiqué haute sévérité le 09-13 (`audit-2026-09-13.md`), corrigé le 09-29 | 16 jours d'exposition de plus | un constat de sécurité haut déjà au journal se traite avant le reste |
| 9 | 2026-08-29 → 09-01 (`…09-01.md`, journal) | F | « cause établie » : `AllowHardTerminate` | correctif insuffisant, même code 0xC000013A revenu ; 3 passes sur le même symptôme | 4 nuits coupées | ne pas écrire « cause établie » sans l'épreuve du correctif |
| 10 | 2026-09-08 puis 2026-10-01 (journal) | F | `reap_stale` corrigé | 2ᵉ chemin : fermait les runs >12 h même vivants | runs vivants marqués `interrompu` | chercher les autres appelants |
| 11 | 2026-10-06 (journal « mauvaise cause ») | F | message du garde-fou Supabase | il nommait la mauvaise cause (budget Disk IO) | 8 h 28 de run | — |
| 12 | 2026-09-08 (journal) | G | lecture de routine | `orchestrator status`/`Ledger()` ont marqué un run **vivant** `interrompu` | donnée du ledger faussée | lire le ledger en `mode=ro` |
| 13 | 2026-08-29 (`…08-29.md`) | G | relance de `test_local_llm` | T1 absent sur ce poste → 0/100 attendu, 28 min | sans impact | tests T1 interdits sur PC2 |
| 14 | 2026-10-06/07 (`…10-07.md`) | D | — | 2 escalades Opus (22:00, 23:00) mortes sur « session limit » ; passe du 07/10 sans étapes 3-4 | 1 jour sans diagnostic | ordre de sacrifice |
| 15 | 2026-10-18 (cette séance) | A' | `sitemap_non_regenere` « à surveiller » | haute ×3 (16-18/10) mais **0 mail, 0 ticket** : `alert.alert` n'est appelé que pour `parseur_casse` (`watch_health.py:178-199`) | 3 nuits sans prévenir | « haute » doit prévenir, sinon ce n'est pas un garde-fou |
| 16 | permanent | E | — | `veille-cycle.py:378` renvoyait à une procédure inexistante dans `CLAUDE.md` | si le SKILL manque, Opus part sans consigne | corrigé (voir §4) |

**Comptes** : A = 6 (+1 A′) · B = 2 · F = 3 · G = 2 · D = 1 passe + 2 escalades vides · E = 1 · H = 1 (inclus au 6).
Dans les 5 premières lignes A, la séance a **bien jugé** après reproduction ;
l'erreur est celle du garde-fou. Le coût propre au réparateur est le retard (6) et
les causes déclarées trop tôt (9-11).

## 2. Branches (ref : `origin/main` = `63f2847`)

Non mergées : `fix/aplatir-non-idempotent-2026-10-16` (1 commit, 10-16),
`feat/repost-resolution-ddproperty` (1, 09-03), `fix/overseer-organize-contract-variants` (1, 09-03),
`origin/fix/overseer-false-muet-detection` (1, 08-09), plus les deux de cette séance.
**Toutes les autres `fix/reparations-*` et `fix/*` sont fusionnées** (ahead=0).
Upstream : seules `fix/rls-vues-security-definer`, `fix/veille-claude-2026-10-04` en ont un.

**Hypothèse C — non confirmée.** Les branches étaient bien **empilées** :
`fix/reparations-2026-10-01` est ancêtre de `…-10-04` ; `fix/reparations-2026-09-26`
(158 commits) a été fusionnée le 09-29, puis `51ff90f` (10-09) et le PR #2 (10-17).
Je n'ai trouvé aucun correctif **refait** d'une branche à l'autre. Le vrai défaut est
ailleurs : de longues périodes où les correctifs vivent hors `main` (09-29 → 10-09), et
quatre commits isolés orphelins depuis 6 semaines à 10 jours. **C'est une décision de
merge, pas une consigne de SKILL.**

## 3. Le SKILL face au tableau

- Dit : tickets un par un, reproduire, branche, test en conditions réelles, mail.
- **Manque** : règle de non-dégradation ; ordre de sacrifice (14) ; méthode « chercher au journal d'abord » ;
  garde « vérifier avant d'enquêter » sur `bloqué/manquant/vide` (types A).
- **Contredit** : « jamais modifier un seuil / une règle de méthode » bloque la correction d'une fausse
  alerte (6) — la correction était un **reclassement**, pas un seuil.
- **Contradiction avec CLAUDE.md** : aucune trouvée (l'heure 01:00/02:30 est déjà datée dans le SKILL).
- Ne dit rien de : lire le ledger en lecture seule (12), branche continue, `claude -p` + `--strict-mcp-config` (7).

## 4. Fait dans ce worktree

- SKILL versionné : `.claude/skills/lowi-reparation/SKILL.md` (copie, aucun secret :
  recherche `password|secret|token|apikey|sk-|postgres://|BASIC_AUTH` → 0).
- (E) corrigé : `ops/veille-cycle.py` — repli = pointeur vers le SKILL du dépôt.
- Proposé, **non appliqué** : `.claude/skills/lowi-reparation/SKILL.proposition.md`.

## 5. Non fait

- Pas de lecture intégrale des ~20 rapports restants ; pas d'application du nouveau SKILL ;
  pas de merge ; pas de changement de `SKILL.md` sous `~/.claude/scheduled-tasks/`.
- Pas de nouvel agent de surveillance (demandé).
- Correctif d'alerte `sitemap_non_regenere` (ligne 15) : non fait — c'est un seuil d'alerte (décision utilisateur).

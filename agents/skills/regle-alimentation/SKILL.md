---
name: regle-alimentation
description: Ajuste le plan d'alimentation Windows actif pour un scrap long — écran off 5 min, veille 5 h, processeur plafonné pour limiter le bruit du ventilateur. Utiliser pour appliquer/revoir ces réglages, ou pour comprendre pourquoi la machine se comporte différemment pendant un cycle.
---

# regle-alimentation

## Mission
Rendre un long cycle de scrap silencieux et sobre en énergie côté matériel
(écran, ventilateur), sans dépendre des privilèges administrateur. Distinct
de `garde-veille` : celui-ci empêche la veille de COUPER un scrap ; celui-ci
règle le CONFORT (bruit, chaleur, écran) autour.

## Étage
**T0 — déterministe.** Famille `Supervision`, mais `lanes: []` dans
`agents.json` : **ne tourne jamais automatiquement**, ni en `daily` ni en
`weekly`. C'est un choix persistant de plan d'alimentation, pas une
correction de bug détectée en cycle — décidé une fois (2026-08-16, à la
demande explicite), pas reconduit à l'aveugle à chaque cycle.

## Invocation
```bash
scraper/.venv/Scripts/python.exe agents/orchestrator.py run regle-alimentation
```

## Procédure
Trois `powercfg /setacvalueindex SCHEME_CURRENT ...` sur le plan ACTIF (le
script ne le nomme pas — il agit sur `SCHEME_CURRENT`, donc sur « Silent »
tant que c'est le plan choisi) :

| réglage | valeur AC | pourquoi |
|---|---|---|
| `SUB_VIDEO/VIDEOIDLE` | 300 s (5 min) | écran off — déjà la valeur du plan « Silent », reposé pour rester correct si le plan change |
| `SUB_SLEEP/STANDBYIDLE` | 18000 s (5 h) | **filet de sécurité**, pas la protection principale |
| `SUB_PROCESSOR/PROCTHROTTLEMIN` | 5 % | processeur au repos entre requêtes — le scrap est I/O-bound |
| `SUB_PROCESSOR/PROCTHROTTLEMAX` | 60 % | plafond pour limiter bruit/chaleur |

Puis `powercfg /setactive SCHEME_CURRENT` pour forcer la réapplication
immédiate (sans ça, certains réglages n'ont d'effet qu'au prochain
changement de plan).

## Pourquoi PROCTHROTTLEMAX et pas la politique de refroidissement
Le levier « attendu » pour un ventilateur silencieux est la politique de
refroidissement (`SYSCOOLPOL`, active/passive). **Mesuré le 2026-08-16** :
`powercfg /setacvalueindex ... SYSCOOLPOL 1` rend le code 0 (aucune erreur),
mais `powercfg /query SCHEME_CURRENT SUB_PROCESSOR 94D3A615-...` renvoie une
liste **vide** — le réglage n'existe tout simplement pas sur ce matériel
(probablement contrôlé par un utilitaire OEM hors de portée de `powercfg`).
Un code retour 0 de `setacvalueindex` **n'est pas une preuve** que le
réglage a pris — vérifié en relisant avec `/query` juste après, pas supposé.
Le plafond de fréquence (`PROCTHROTTLEMAX`), lui, est confirmé présent et
modifiable sur ce poste.

## Contrat de sortie
```json
{"reglages": [{"reglage": str, "valeur": str, "exit": int, "pourquoi": str}, ...],
 "tous_ok": bool,
 "activation_exit": int}
```

## Bandes normales
`tous_ok: true` systématiquement attendu — `powercfg /setacvalueindex` sur
le plan courant ne demande pas d'élévation (vérifié sans droits admin le
2026-08-16, contrairement à `powercfg /requests`). `false` = à investiguer :
GPO qui verrouille le plan d'alimentation, ou `powercfg` absent du PATH.

## Modes de panne connus
- **Code retour 0 mais réglage sans effet** : c'est arrivé pour SYSCOOLPOL
  (voir ci-dessus). Ne jamais faire confiance au seul code retour de
  `setacvalueindex` pour un nouveau réglage — revérifier avec `/query`.
- **Un changement de plan d'alimentation actif** (l'utilisateur bascule sur
  « Équilibré » ou « Performances ») annule ces réglages : ils vivent sur le
  plan `SCHEME_CURRENT` au moment de l'appel, pas sur un plan nommé. Relancer
  le script après tout changement de plan si on veut les mêmes réglages.
- **DC (batterie) non touché** : le script ne règle que l'index AC. Sur
  batterie, les valeurs d'origine du plan restent en vigueur.

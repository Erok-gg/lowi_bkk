# scraper/social — collecte brute des groupes Facebook immo Bangkok

Rapatrié de `C:\agentic\agents\agent2_scraper` le **2026-09-13** (audit du
même jour : la tâche Windows vivait hors dépôt, inconnue de la doc, et
rendait 0x1 chaque nuit alors que son log disait « ok »).

## Ce que ça fait
`LowiBKK-ScrapeImmoFacebook` (quotidienne 01:00, `ops\install-facebook-task.ps1`)
lance `scrape-immo-facebook.ps1` :
1. ferme **tout** Chrome (le port CDP 9222 doit être libre) ;
2. ouvre Chrome sur le profil `%USERPROFILE%\ChromeAutomationProfile`
   (connecté à Facebook **à la main, une fois** — jamais le profil principal) ;
3. `node facebook/agent.js` : 5 groupes (`immo-groups.json`), 7 jours,
   collecte brute (`FB_SKIP_ANALYSIS=1` — aucun Ollama, PC2 n'en a pas), 30 min max ;
4. écrit `scraper/output/social/immo_YYYY-MM-DD.json` et
   `scraper/social/logs/sonde-immo.json` (conteneurs vs posts par groupe :
   des conteneurs sans post = casse DOM Facebook, pas un groupe silencieux).

**Le code retour de la tâche est celui du scrape** (0 = ok). Journaux :
`ops/logs/facebook/`.

## Aval (manuel pour l'instant)
- `node immo-extract.mjs <immo_YYYY-MM-DD.json>` → `*_extrait.json` (extraction
  structurée ; conçu pour un modèle — la « routine Claude/Haiku planifiée »
  annoncée le 2026-09-12 **n'existe pas** dans les routines au 2026-09-13).
- `node immo-resolve.mjs <*_extrait.json>` → `*_resolu.json` : rapproche les
  immeubles des condos de `scraper/output/bangkok.db` (lecture seule) et
  compare aux médianes.
- `python scraper/load_social_leads.py <*_resolu.json> --sqlite` →
  `scraper/output/social-leads.db`, base **séparée** de la référence.

## Fichiers
- `facebook/agent.js`, `utils/*` : **copies** — l'original reste dans
  `C:\agentic` pour la veille Equance ; un correctif fait d'un côté ne se
  propage pas tout seul.
- `config.js` : dégraissé (plus de groupes Equance, WhatsApp, LinkedIn).
- `diag/` : sondes DOM du 2026-09-12 (les .json/.png sont gitignorés).
- `node_modules/` : `npm install` ici (playwright, chalk, date-fns, node-fetch) — gitignoré.

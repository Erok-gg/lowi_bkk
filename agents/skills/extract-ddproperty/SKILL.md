---
name: extract-ddproperty
description: Extraction DDproperty (vente et location) vers Supabase. Parsing __NEXT_DATA__ derrière un challenge Cloudflare, avec géocodage. Utiliser pour lancer, diagnostiquer ou réparer le scrap DDproperty.
---

# extract-ddproperty

## Mission
Mettre à jour les annonces DDproperty (~11 700 annonces, 6 700 actives).
**Seule source qui expose `agent_id`, `agency_id`, `posted_at` et `is_auto_repost`** —
elle porte donc la vérité terrain qui rend la question des doublons décidable.

## Étage
**T0 — déterministe.**

## Entrées
`scraper/config/ddproperty.json` · `scraper/config/targets/ddproperty-corridors.json`

## Procédure
1. `run.py --source ddproperty --deal-type <deal> --full --geocode --store supabase`
2. **Puis** passe ciblée couloirs (même raison que FazWaz : restauration).
3. **Puis** recensement : `recense.py --source ddproperty --onglets 5 --store sqlite --delister`.

### Le recensement (étape 3, ajoutée le 2026-08-23)
Nos 150 pages couvrent **2,7 %** du catalogue (2 748 pages en vente, 2 899 en
location, ~113 000 annonces — mesuré par dichotomie le 2026-08-23). Le garde-fou
anti-délistage de `run.py` s'annule donc à chaque cycle (scan à 16 % des actives,
seuil à 50 %) et le stock ne fait que monter : 6 671 actives le 31/07, 32 142 le
22/08. Le recensement énumère les identifiants du catalogue entier **sans ouvrir
une seule page détail** : 1 h 35 à 5 onglets (1,01 s/page mesurée contre 5,24 s à
un onglet).

Ce qu'il fait depuis le **2026-09-13** (`--delister`, `recense._delister`) :
- **délistage avec grâce de 3 nuits consécutives** d'absence du catalogue,
  rien supprimé, photos gardées. La mesure du 23/08 (« 10 actives sur 12 non
  revues encore en ligne ») datait d'un recensement qui **ne rafraîchissait
  rien** dès qu'une page manquait (corrigé le 09/09) : « non revue » ne
  voulait alors pas dire « absente ». Re-mesuré le 13/09, recensement sain :
  **16/16 actives absentes depuis 3 à 60 j sont mortes** (12 × HTTP 404,
  4 × page sans `listingDetail`) contre **4/4 vivantes** parmi les revues la
  veille. Abstentions explicites : page terminale non atteinte, > 1 % de
  pages trouées, < 50 % des actives revues.

Ce qu'il **ne fait pas**, et c'est voulu (arbitrage du 2026-08-23) :
- **aucune insertion** — les inconnues partent dans
  `output/recensement/ddproperty-inconnues.jsonl`. Les enregistrer toutes
  pèserait ~540 Mo sur une base à 810 Mo en formule gratuite (mesuré).
- **aucune résurrection** — seules les lignes déjà `active` sont rafraîchies.

## Contrat de sortie
```json
{"nouvelles": int, "changees": int, "retirees": int, "traces_erreur": int, "then_exit": int,
 "pages_lues": int, "annonces_vues": int, "absentes_du_catalogue": int,
 "inconnues_de_la_base": int}
```
Les quatre derniers viennent du bilan JSON du recensement (étape 3), lu par
`agents/core/shell.py`. Ils ne portent **pas** les mêmes noms que les compteurs
d'extraction à dessein : `aplatir()` additionne `nouvelles`/`retirees` entre
étapes, et mélanger un recensement de 113 000 identifiants aux nouvelles d'un
scan ferait exploser les bandes de `watch-health` pour rien.

## Bandes normales
`nouvelles` 30–1500 · `traces_erreur` 0–3

## Escalade
- `nouvelles` = 0 avec `traces_erreur` = 0 → ticket `parser_break`.
- Beaucoup d'erreurs HTTP 403 → ticket `cloudflare` : la session réchauffée ne
  prend plus, il faut revoir la stratégie d'en-têtes.

## Modes de panne connus
- **Challenge Cloudflare** sur les pages détail. Contourné sans Chrome par une
  session `requests` réchauffée (parcourir la liste d'abord → cookie `__cf_bm`)
  avec en-têtes navigateur et **sans brotli** (requests ne le décode pas).
  C'est fragile par nature : c'est la panne à surveiller en priorité.
- `robots.txt` illisible derrière le challenge → accès autorisé par défaut (RFC).
- `tenureCode='F'` → freehold gardé, leasehold écarté. Quota non exposé (None).

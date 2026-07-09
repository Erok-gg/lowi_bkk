# Sources officielles récurrentes (croisées avec la base Lowi)

> Documenté le 2026-07-09. Le fetch automatique vit dans `study/fetch_official.py`
> (appelé par `run_study.py` ; peut aussi se lancer seul).

## 1. DOPA / BORA — population par khet ✅ AUTOMATISÉ
- **Quoi** : population enregistrée (ทะเบียนราษฎร) par district, mensuelle, historique 1998+.
- **Cadence** : mensuelle (dispo ~milieu du mois suivant).
- **Granularité** : khet (et khwaeng).
- **Accès** : API non documentée de la SPA officielle, découverte 2026-07-09 :
  `https://stat.bora.dopa.go.th/stat/statnew/connectSAPI/stat_forward.php?API=/api/statpophouse/v1/statpop/list?action=24&yymm=<YYMM_bouddhiste>&nat=999&popst=99&cc=10&rcode=<1001..1050>`
  - `yymm` : année bouddhiste 2 chiffres + mois (ex. 6906 = juin 2026). `action=24` = vue district (2 lignes H/F, champ `lsSumTotTot`).
  - ⚠ le WAF (F5) rejette les URL sur-encodées → passer l'URL BRUTE (voir fetch_official.py) ; User-Agent navigateur + Referer requis.
  - Liste des districts : `.../v1/list?action=2&cc=10` (codes TIS-1099 → mapping `khet-codes.json`).
- **Croisements** : annonces vente & location / 1000 habitants (sur-offre réelle), Δ population 12 mois (quartiers qui se vident/se remplissent).
- **TODO** : endpoint « maisons » (stathse…) → ménages par khet (le path exact reste à trouver, 404 sur nos essais).

## 2. Bank of Thailand — indices prix résidentiels (RPPI) ⚙ SEMI-AUTO
- **Quoi** : indice condo BKK (hédonique, données de prêts) + maisons/townhouses. Mensuel.
- **Accès** : [portail API officiel](https://portal.api.bot.or.th/) — **gratuit mais nécessite un compte + clé**
  (à créer, puis poser `BOT_API_KEY` dans `scraper/.env` — le fetch la prendra tout seul, série RPPI).
  En attendant : saisie manuelle trimestrielle dans `study/official/bot-manual.json`
  (source : [BOTWEBSTAT reportID 920](https://app.bot.or.th/BTWS_STAT/statistics/BOTWEBSTAT.aspx?reportID=920&language=ENG)).
- **Croisement** : nos médianes 0-1BR vs indice officiel → mesure de l'évolution de la marge de négociation
  (nos prix = affichés ; l'indice = transactions financées).

## 3. Treasury Department — valeurs cadastrales 📌 PONCTUEL (cycle 4 ans)
- [assessprice.treasury.go.th](https://assessprice.treasury.go.th/) + D-Value (certificats gratuits).
- Par parcelle/rue et par immeuble de condo. Cycle 2023-2026, **reset 2027 à surveiller**
  (photo officielle de la revalorisation des couloirs métro).
- Croisement cible : prix demandé / valeur cadastrale sur les fiches d'opportunités (à outiller plus tard).

## 4. REIC — transferts & absorption 📖 LECTURE TRIMESTRIELLE
- [reic.or.th](https://www.reic.or.th) — transferts réels (dont étrangers par nationalité), absorption,
  stock invendu. BMR, pas khet. Détail payant ; chiffres clés reprises presse à chaque trimestre.
- À reporter à la main dans `study/context.md` quand un chiffre marquant sort.

## 5. BMA Open Data — permis de construire par khet 📖 ANNUEL
- [data.bangkok.go.th](https://data.bangkok.go.th/) (CKAN + API). Pipeline d'offre future par quartier.
- Qualité/fraîcheur inégales → vérifier le jeu de données avant d'automatiser.

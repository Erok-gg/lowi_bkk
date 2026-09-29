# Masterlog — registre des demandes

> **Ne pas lire par défaut.** Ce fichier n'est consulté que sur demande
> explicite (« regarde le masterlog », « qu'est-ce que j'avais demandé le… »).
> Il n'est chargé dans aucun contexte automatiquement et n'a pas à être
> parcouru en début de séance. `CLAUDE.md` n'en donne que le pointeur.
>
> **Ce qu'il est** : la liste horodatée des demandes, une ligne chacune, dans
> les mots de la *demande* — pas dans ceux de la réalisation.
>
> **Ce qu'il n'est pas** : ni le journal technique (qui porte le *pourquoi*,
> les mesures et les limites), ni `git log` (qui porte le *quoi* livré). Une
> demande refusée, abandonnée ou restée sans suite y figure au même titre
> qu'une autre — c'est précisément ce qui le rend utile : il montre ce qui a
> été voulu, y compris quand rien n'en est sorti.
>
> **Convention d'écriture**
> - Une ligne par demande. Append-only, comme le journal : on ne réécrit pas
>   une demande passée, on ajoute la suivante.
> - Horodatage à la minute, fuseau Bangkok (UTC+7). Un `~` marque une heure
>   approchée (demande enregistrée après coup, dans la même séance).
> - Colonne « Suite » : où vit la réponse (entrée de journal, commit, ou
>   « sans suite » / « refusée » / « laissée à l'arbitrage »).
> - La demande est consignée **telle qu'elle a été formulée**, même si la
>   mesure l'a ensuite contredite. La correction va dans la colonne Suite.
>
> **Départ du registre : 2026-08-26.** Les demandes antérieures n'ont pas été
> reconstituées : les réinventer après coup contredirait la règle 1 du
> `CLAUDE.md` (mesurer avant d'affirmer). Pour ce qui précède, les sources
> sont `docs/journal-technique.md` et `git log`.

---

## 2026-08

| Horodatage | Demande | Suite |
|---|---|---|
| 2026-08-26 ~13:05 | Confirmer l'architecture : l'utilisateur accède à la carte via Vercel, la DB reste sur PC2, le site charge ses requêtes depuis la DB de PC2 | **Infirmée par mesure.** Réponse initiale fausse (bâtie sur un `CLAUDE.md` périmé). Journal 2026-08-26 (suite 3) |
| 2026-08-26 ~13:10 | Rectification : Supabase est dépassée, le dernier scrap a écrit en local sur PC2 ; les infos vitales remontent vers Vercel à chaque scrap ; une requête non supportée par Vercel interrogerait PC2 | **Point 1 confirmé** (serveur gelé au 22/08, écart 7 767 annonces). **Points 2 et 3 infirmés** : remontée non branchée, aucun chemin Vercel→PC2. Journal 2026-08-26 (suite 3) |
| 2026-08-26 ~13:15 | Remettre l'architecture en ordre avant de continuer : refaire `CLAUDE.md` en ce sens, inscrire la modif au journal, instaurer un masterlog des demandes (concis, horodaté, consulté sur demande seule). Rappel des principes permanents : tout modulaire, tout réversible, la data protégée, Vercel sous son free tier, audit de structure après chaque milestone (sécurité des appareils et de Vercel) | `CLAUDE.md` refait (architecture + règles 7 à 10), ce fichier créé, journal 2026-08-26 (suite 3). **Remise en service du flux de données non faite** — laissée à l'arbitrage |
| 2026-08-26 ~13:35 | Chiffrer les options de périmètre pour la remontée PC2 → Supabase | 4 scénarios chiffrés sur coût/ligne relevé au serveur. **Mon affirmation antérieure sur le quota infirmée.** Recommandation C (157 Mo, 31 %). Journal 2026-08-26 (suite 4). **Rien remonté** — arbitrage en attente |
| 2026-08-26 ~13:40 | Faire un md de référence pour les calculs et leurs justifications | `docs/methodes-calculs.md` créé (10 sections : bornes, double médiane, within-condo, cross-match, décotes, tension, cohortes, ce qu'on ne calcule pas, récap des constantes) |
| 2026-08-26 ~13:40 | Vider le journal technique, en laissant un résumé des grandes étapes | Fait **avec réserve exprimée** (règle 3 append-only + traçabilité d'antériorité) : contenu intégral copié dans `docs/journal-technique-archive-2026-06_08.md` (3 380 lignes), journal courant réduit au résumé + entrées courantes. **Suppression de l'archive non faite — à confirmer** |
| 2026-08-26 ~13:55 | Retenir le scénario A pour la remontée ; les annonces non actives servent aux statistiques d'évolution du marché dans le temps, donc restent locales | **A implémenté** (`--statut actives` + `--synchro-statuts`). Deux défauts trouvés en codant : l'upsert ressusciterait les délistées (C était dangereux), et A laisse ~1 876 fantômes actives (400/400 vérifiés). Débit mesuré 4,1/s → ~3 h 40. **Pilote de 500 seulement — remontée complète non lancée.** Journal 2026-08-26 (suite 5) |
| 2026-08-26 ~14:20 | Mettre la remontée en lane `daily` après le scrap, et repousser la veille en conséquence | Agent `remonter-supabase` inséré en tête de « suite » (ordre vérifié en dry-run). `STANDBYIDLE` 5 h → 13 h, appliqué **et vérifié** (`0xb6d0`). Défaut créé par le changement et corrigé : `scrap_en_cours()` ne couvrait pas la fenêtre de 4 h → `LONGS_A_NE_PAS_COUPER`. Journal 2026-08-26 (suite 6) |

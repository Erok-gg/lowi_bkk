# Lowi BKK — Dossier données & méthode

> Dossier destiné à un lecteur extérieur : investisseur, partenaire, acquéreur
> potentiel de la brique données. Il décrit **ce qui existe et fonctionne**, mesuré
> au 2026-07-31, et **dit explicitement ce qui n'existe pas encore**.
>
> Écrit pour être opposable en due diligence. Chaque chiffre est reproductible
> depuis la base ; les limites sont dans un document dédié, pas en note de bas de page.

## Les documents

| | |
|---|---|
| [01 — Le flux de données](01-flux-de-donnees.md) | De la page web au chiffre affiché. Les cinq étapes, ce que fait chacune, où c'est automatisé |
| [02 — La méthode et ce qui la différencie](02-methode-et-differenciation.md) | Pourquoi ces chiffres sont plus solides que ceux d'un agrégateur. Cinq partis pris méthodologiques |
| [03 — Valeur et monétisation](03-valeur-et-monetisation.md) | Ce qui est vendable, ce qui ne l'est pas, et pourquoi cette distinction est structurante |
| [04 — Limites connues](04-limites-connues.md) | Ce qui manque, ce qui est fragile, ce qui est un artefact. À lire avant de s'engager |
| [05 — Ce que ça représente comme travail](05-effort-et-perimetre.md) | Volumes mesurés, effort équivalent estimé, et la part de l'effort qui ne produit aucune ligne de code |

**L'historique de développement n'est pas dans ce dossier** : il vit dans le
[journal technique](../journal-technique.md), registre append-only tenu depuis le
début — 68 commits sur six semaines. On n'y réécrit jamais le passé : une décision
qui s'est révélée fausse y reste, suivie de l'entrée qui la corrige. C'est
volontaire, et c'est en soi un élément de due diligence : il montre comment les
défauts ont été trouvés, en combien de temps, et ce qui a été mesuré pour trancher.

## En une page

**Ce que c'est.** Une infrastructure qui observe le marché du condominium à
Bangkok en continu, quatre sources, et en tire des séries statistiques par
quartier et **par immeuble**.

**L'état, mesuré le 2026-07-31.**

| | |
|---|---|
| Annonces observées | **35 813** dont **18 879 actives** |
| Périmètre assaini (utilisable en statistique) | **18 525** |
| Immeubles au référentiel | **4 514** |
| Immeubles avec vente **et** location actives | **1 308** |
| Observations de prix historisées | **36 505** |
| Annonces avec mouvement de prix observé | **736** (amplitude moyenne 8,9 %) |
| Cohortes suivies dans le temps | **9 385**, soit **80 126** observations |
| Profondeur de série | **6 semaines** (depuis le 2026-06-21) |

**Ce qui a de la valeur.** Pas les annonces — n'importe qui peut les scraper. La
valeur est dans quatre choses que presque personne ne fait :

1. **L'immeuble comme unité d'analyse**, pas l'annonce. Un immeuble = une voix,
   ce qui neutralise le biais des immeubles sur-représentés.
2. **L'appariement vente ↔ location dans le même bâtiment** (1 308 immeubles) :
   un rendement réel, pas un ratio de deux médianes qui ne parlent pas du même parc.
3. **Le suivi par cohorte** (9 385 cohortes) : mesurer l'écoulement du stock sans
   se faire tromper par les republications d'annonces.
4. **Un périmètre de plausibilité unique**, appliqué partout de la même façon.

**Ce qui n'est pas vrai aujourd'hui**, et qu'il ne faut pas laisser croire :
la série n'a que six semaines ; les annonces brutes **ne sont pas revendables** ;
l'année de construction n'est renseignée nulle part. Détail en
[04 — Limites connues](04-limites-connues.md).

**Le degré d'automatisation.** Depuis le 2026-07-31, douze agents orchestrés
tournent sur une cadence de quatre jours, avec journal d'exécution et détection
de panne. Avant cette date, tout était lancé à la main — trois tâches planifiées
existaient mais n'avaient jamais fonctionné. Voir
[agents/README.md](../../agents/README.md).

# Règles de construction — bilan acheteur (beta)

> Tenu **au fil de la construction** (demande de l'utilisateur, 2026-10-17).
> Une règle qui change se corrige ici, avec la date et le pourquoi.
> Retour au projet : [README](README.md) · Contenu du bilan : [journal-produit-ui](journal-produit-ui.md).

## 1. Parcours
1. **`/beta`** : landing avec un seul champ, « paste the link of a listing ».
2. Envoi → **chargement** : les éléments calculés défilent pendant que le rapport se génère.
3. **`/beta/r/<id>`** : le bilan. **Même URL sur mobile et sur PC**, la disposition change avec la largeur d'écran.
4. **Gros bouton « Get the full PDF report »** → `/beta/r/<id>/pdf` : tous les blocs dépliés, toutes les explications, mise en page A4, impression en PDF.

## 2. Mise en page
| Écran | Largeur | Disposition |
|---|---|---|
| Mobile | < 1024 px | une colonne ; blocs repliables (les barres de signaux n'apparaissent **qu'au dépliage**) ; bouton PDF **collé en bas d'écran** |
| PC | ≥ 1024 px, pensé pour **1920 × 1080** | grille 12 colonnes : colonne gauche (4) collante avec identification, verdict et chiffres clés ; zone droite (8) en deux colonnes de blocs, tous dépliés ; bouton PDF dans l'en-tête de la colonne gauche |
| PDF | A4 portrait | tout déplié, aucun bouton, explications « How is this computed? » imprimées sous chaque bloc |

## 3. Données affichées
- **Anglais uniquement** (règle du site).
- **Chaque chiffre porte son effectif** (« n = 27 ») et chaque score sa **fourchette**.
- Mentions obligatoires : « Asking prices, not sold prices » ; « Monthly calculation · data as of <date> » ; « Lowi takes nothing from the seller ».
- Un niveau sans assez de données s'affiche **« not enough data »**, jamais un chiffre nu.
- **Aucun lien vers les annonces comparables** (choix juridique et produit).

## 4. Génération
- `study/tension/rapport.py --url <URL> --db <base> --out <dossier>` écrit `<id>.json`. Identifiant = 16 premiers caractères du SHA-256 de l'URL : même URL, même rapport.
- **Tension et liquidité** viennent du fichier mensuel `scores-tension/scores-latest.json`, situé à côté de la base. Seuls l'historique de l'annonce, le prix face aux comparables et les drapeaux sont calculés à la demande (environ 10 s, mesuré).
- **Historique de l'annonce** : la cohorte n'est pas le lot. Mesuré : 97 annonces dans « The Lumpini 24, 2 ch., 55 m² ». Deux annonces sont le même lot si elles ont le même étage (quand il est connu), la même surface à ±1 m² et le même prix à ±5 %, et se recouvrent ou se suivent à moins de 14 jours.
- **Comparables** : au niveau de l'annonce, en dédoublonnant les copies (même immeuble, chambres, surface arrondie, étage, prix à 10 000 THB près), en excluant les copies de l'annonce visée.

## 5. Chargement
- Il fait défiler **les 8 calculs réellement faits** (portails, historique, comparables, prix/m², tension, revente, vendeurs dans l'immeuble, drapeaux) : il explique ce qu'on obtient, il ne fait pas patienter avec du vide.
- Il dure **au moins un tour lisible** (6,5 s) et s'arrête dès que le rapport est prêt. Au-delà de deux tours : « Taking longer than usual ». Au-delà de 5 min, le serveur déclare le calcul mort (mesuré : ~10 s).
- Appels : `POST /api/beta/analyse {url}` → `{id, etat}` ; `GET /api/beta/analyse?id=` toutes les 0,9 s.

## 6. PDF
- **Bouton or, pleine largeur, 56 px de haut, halo** : le seul élément doré de la page. Collé en bas d'écran sur mobile, dans la colonne gauche sur PC.
- `/beta/r/<id>/pdf` ouvre la boîte d'impression ; le PDF est produit par « Save as PDF » du navigateur. **Pas de rendu serveur** (Puppeteer) pendant la beta : aucune dépendance lourde, et Vercel n'a de toute façon pas les données.
- Règles d'impression (`globals.css`, `@media print`) : A4, marges de 10 mm, couleurs conservées, et **aucun conteneur à hauteur fixe**, sinon une seule page sort. Le header du site est masqué (`print:hidden`).

## 7. Disposition PC — détails
- Conteneur `max-w-[1880px]` (1920 moins 2 × 20 px), colonne gauche **collante**, blocs en deux colonnes à partir de 1280 px (`xl`), une seule entre 1024 et 1280.
- Entre 1024 et 1280 px, blocs pleine largeur : jamais de bloc plus étroit que ~420 px (la réglette de prix devient illisible en dessous).

## 8. Mobile — détails
- Testé dans un vrai cadre de 390 px. ⚠ Chrome sans interface impose ~500 px de largeur minimale : une capture `--window-size=390` montre un faux débordement.
- La navigation du site défile horizontalement sur mobile (sinon elle élargissait tout le document).
- Le bloc prix est ouvert par défaut ; les autres sont repliés, avec leur résumé (score, première vue) visible.

## 9. Données et accès pendant la beta
- **Ne fonctionne que sur PC2** : Next lance Python (`LOWI_PYTHON`, défaut `scraper/.venv`) sur la base `LOWI_SQLITE_DB`, et écrit les rapports dans `<dossier de la base>/rapports` (ou `LOWI_RAPPORTS_DIR`). Sur Vercel, l'API répond 503 avec un message clair.
- L'URL collée n'est jamais passée à un shell : arguments en tableau, portails autorisés en liste blanche.
- Pages derrière le mot de passe du site (`isAuthed`), comme le reste.

## 10. Défauts trouvés en construisant (et corrigés)
- Historique : la cohorte agrégeait 97 annonces de lots distincts → règle du « même lot » (§4).
- Comparables « même immeuble, même surface » à 0 : ils étaient dans la cohorte de l'annonce, qu'on excluait → comparaison au niveau de l'annonce.
- Mobile : débordement causé par la nav du site ; champ URL écrasé en hauteur dans la colonne flex.
- « Price change » affichait +1 % malgré une baisse : la première observation venait d'un autre portail, à un autre prix. Libellé corrigé en « Since first seen ». La variation reste multi-portails, à revoir.

## 11. Pas encore fait
- Paiement, compte, envoi du PDF par mail : la beta montre tout, sans verrou.
- Niveaux « même surface » de la tension (uniquement dans le bilan complet en ligne de commande).
- Sections payantes spécifiées mais non construites : perspectives patrimoniales, hidden costs, location et simulateurs.
- Texte SVG trop grand dans le PDF (les réglettes s'élargissent à 190 mm) : hauteur à fixer.
- Un score dont la fourchette est trop large (« not enough data ») s'affichait quand même (liquidité 89, fourchette 10–100) : **un score n'est montré que s'il a un libellé**, en tête comme dans les comparaisons par niveau.

## 12. Premier lot mensuel réel (2026-10-17, fenêtre au 12/10)
2 896 immeubles en **19 min** (mesuré ; estimation précédente : ~50 min), 0 erreur, fichier de 9,3 Mo. Bilan test : tension 43 « balanced » à 1 km (n = 126 groupes, 11 sorties), 41 à Bangkok, 36 dans le CBD ; liquidité non publiée, comme prévu.
- **Noms d'immeubles** : rapprochés par nom normalisé (`_norm_condo`, la règle de `unit_key`), jamais par nom brut. FazWaz « Noble Ploenchit » et DDproperty « Noble Ploenchit, Bangkok » se perdaient : comparables de l'immeuble 32 au lieu de 206, tension et année introuvables (démo du 2026-10-17). Corrigé dans le rapport et dans le lot mensuel (champ `cle`).

## 13. Délai de livraison mesuré (démo du 2026-10-17, PC2, serveur de dev)
| Étape | Temps |
|---|---|
| Envoi de l'URL → réponse de l'API | 0,26 s |
| Rapport calculé (nouvelle URL) | **10,4 s** |
| Écran de chargement (durée minimale volontaire) | 6,5 s, donc masquée par le calcul |
| Affichage du bilan | 0,3 s (1re visite), 0,2 s ensuite |
| Même URL redemandée | 0,2 s (rapport déjà calculé, rien n'est recalculé) |

## 14. Demandes simultanées (mesuré le 2026-10-17, PC2, 8 cœurs, serveur de dev)
Pas de file d'attente : chaque nouvelle URL lance son propre processus Python, en parallèle des autres. Une même URL demandée deux fois ne lance qu'un calcul (marqueur `.pending`).
| Demandes simultanées | Dernier rapport prêt |
|---|---|
| 1 | 10,4 s |
| 3 | 18,5 s |
| 6 | 28,1 s |
Tout passe, mais chaque demande ralentit les autres : les processus se partagent les cœurs et relisent chacun le fichier mensuel de 9,3 Mo et la base. **Aucune limite n'existe** : 30 demandes d'un coup lanceraient 30 processus, y compris pendant le cycle de nuit.
**Fait le même jour** : plafond à 6 et file (§15). **Reste** : un processus de calcul permanent qui garde les scores en mémoire au lieu de les relire à chaque demande.

## 15. File d'attente (décision de l'utilisateur, 2026-10-17)
- **Au plus 6 calculs en parallèle** (`MAX_PARALLELE`, `lib/beta/rapport.ts`) ; au-delà, file en mémoire du serveur Next, servie dans l'ordre d'arrivée. Une URL déjà calculée, en cours ou en file ne relance rien.
- **Affiché pendant le chargement** : rang dans la file (« 2 of 3 »), calculs en cours (« 6 / 6 »), rapports traités (total et du jour, comptés sur les fichiers produits), temps restant estimé ; recalculés à chaque interrogation (0,9 s). En file, le défilement des calculs est en pause (« Waiting for a free slot »).
- **Estimation** : t(k) = 6,5 + 3,6·k s pour k calculs simultanés, ajustée sur les mesures (10,4 / 18,5 / 28,1 s pour 1 / 3 / 6). En file : temps jusqu'à la libération de **sa** place, plus son propre calcul avec ceux qui partent en même temps. Une première version par débit moyen annonçait 33 s pour 52 s réelles. **Essai à 9 demandes simultanées** : 6 prêtes à 26–28 s, 3 en file prêtes à 45–46 s, annoncées 35 à 42 s au moment du dépôt.
- **Limite connue** : la file est perdue si le serveur redémarre ; le chargement le dit au bout de 15 s (« The server restarted… submit it again »). La file n'est **pas** partagée entre plusieurs instances du serveur (sans objet tant que tout tourne sur PC2).

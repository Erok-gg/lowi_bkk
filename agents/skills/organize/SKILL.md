---
name: organize
description: Réconcilie les données entrantes — backfills géocodage, arbitrage des doublons en mode extraction, alignement des bornes de plausibilité. N'écrit aucune fusion ni suppression. Utiliser après un cycle d'extraction.
---

# organize

## Mission
Tenir la base propre **sans jamais rien détruire**.

## Étage
**T0 + T1.** Les backfills sont déterministes. L'arbitrage des doublons utilise
le modèle local, mais **en mode extraction** : le modèle constate des faits, le
code décide.

## Entrées
`listings`, vues `doublons_agent`, `listings_sane` · `lib/market-bounds.ts`

## Procédure

### 1. Backfills (déterministe)
Géocodage manquant, années de construction, re-matching khet sur nouvelles coordonnées.
Ne remplit que le manquant — **n'écrase jamais une coordonnée précise**.

### 2. Alignement des bornes
Vérifier que `lib/market-bounds.ts` et la vue `listings_sane` disent la même
chose. Toute divergence = `finding` de sévérité haute : les deux sont la source
unique de vérité du périmètre, un écart fausse toutes les statistiques.

### 3. Arbitrage des doublons — LE PRÉ-FILTRE SQL EST OBLIGATOIRE
Sur ~38 000 paires candidates, le SQL en tranche ~10 000 **gratuitement et sans
erreur** :

- les deux annonces **actives simultanément** → lots distincts ;
- l'une **retirée**, l'autre apparue **après** ce retrait, prix à moins de 2 %
  → republication.

**Ne jamais soumettre au modèle une paire que le SQL tranche.** Il coûterait
3,6 s pour faire moins bien.

### 4. Le résidu ambigu — MODE EXTRACTION UNIQUEMENT
Le modèle ne rend **pas** de verdict. Il renseigne six faits :
`a_active`, `b_active`, `a_retiree`, `b_retiree`, `b_apres_a`, `ecart_prix_pct`.
Le code décide ensuite.

Mesuré sur 100 paires réelles : verdict direct 92 % mais **0 % d'abstention** ;
extraction 91 % et **77 % d'abstention**. L'écart de justesse n'est pas
significatif, l'écart d'abstention est décisif.

### 5. File de revue
Les ~23 % de paires ambiguës qui reçoivent malgré tout un verdict vont dans
`agents/state/organize/revue.jsonl`. **Elles n'influencent aucune statistique.**
Elles attendent une validation humaine.

## Contrat de sortie
```json
{"backfills": int, "bornes_alignees": bool, "paires_sql": int,
 "paires_modele": int, "abstentions": int, "revue_ajoutee": int, "pannes_llm": int}
```

## Bandes normales
`abstentions` / `paires_modele` ≥ 70 %. **En dessous, le modèle invente des
certitudes → `finding` haute sévérité et arrêt de l'étage T1.**

## Escalade
- Bornes désalignées → ticket `bornes_divergentes`, sévérité haute.
- Taux d'abstention < 70 % → ticket `modele_derive`.

## INTERDITS ABSOLUS
- **Aucune fusion. Aucune suppression. Aucun `status` modifié.** Findings seulement.
- Le 2026-07-28, « 1 399 doublons exacts » s'est révélé être des **lots distincts**
  versés en lot par une agence (identifiants FazWaz consécutifs `u6548791…u6548800`,
  tous actifs en même temps). Une dédup aurait **effacé de l'offre réelle** —
  c'est-à-dire exactement ce que la pression vendeuse doit compter.
- Deux annonces identiques du **même agent** sont un doublon ; les mêmes venant
  d'agences concurrentes sont deux mises en marché. Sans `agent_id`, on ne tranche pas.

## Modes de panne connus
- `agent_id` n'existe que sur DDproperty (1 294 annonces). Les 3 autres sources
  ne permettent pas la dédup même-agent.
- La `confidence` rendue par le modèle **n'est jamais un seuil** : qwen2.5:7b
  rendait 0,9 sur des réponses fausses.

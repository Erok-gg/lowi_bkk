"""metrics.py — lire les métriques d'un run SANS dépendre de leur forme.

POURQUOI CE MODULE EXISTE
Le 2026-08-06, le chaînage `then` (agents.json v2 : vente PUIS location dans le
même agent) a rangé les métriques des agents T0 sous ``{"etapes": [...]}``. Les
deux surveillances, elles, ont continué de lire à la RACINE.

Mesuré le 2026-08-23 sur le ledger : 24 runs d'extraction sur 5 cycles avec
``nouvelles = None`` — donc verdict `metriques_absentes` (medium, muet) au lieu
de `parseur_casse` (high), le SEUL verdict qui escalade et envoie un mail.
Nestopa ramenait 0 annonce depuis le 2026-08-17 sans que rien ne parle. Même
cause côté overseer : 13 contrats comptés violés sur 23 runs le 2026-08-22,
champs présents un étage plus bas. Trois semaines de surveillance inerte —
c'est exactement le mode de panne de la règle 2.

APLATIR À LA LECTURE, PAS SEULEMENT À L'ÉCRITURE
`watch-health` prend la médiane des 10 derniers runs : cet historique est déjà
en base sous la forme imbriquée. Corriger la seule écriture aurait laissé la
médiane fausse pendant 10 cycles, soit ~6 semaines à cette cadence.
"""
from __future__ import annotations

import json

#: Champs qu'on ADDITIONNE entre étapes chaînées. Liste explicite à dessein :
#: sommer aveuglément inventerait des totaux faux (un ratio, un âge en jours,
#: un volume de base ne s'additionnent pas). Tout champ numérique hors liste
#: prend la valeur de la dernière étape plutôt qu'un total qui ne veut rien dire.
SOMMABLES = frozenset({
    "scannees", "nouvelles", "changees", "retirees", "exclues",
    "inchangees", "dedup",
    "erreurs_http", "erreurs_images", "lignes_log", "traces_erreur",
    "lignes_purgees", "lignes_archivees",
})


def aplatir(metrics: dict) -> dict:
    """Rend les métriques avec les champs d'étape remontés à la racine.

    Sans clé ``etapes`` (agents T1, qui rendent déjà un dict plat) : identité.
    Les étapes restent présentes sous ``etapes`` — l'agrégat s'AJOUTE à la
    trace, il ne la remplace pas : sinon on perdrait quelle étape a cassé.
    """
    etapes = metrics.get("etapes")
    if not isinstance(etapes, list) or not etapes:
        return metrics

    plat = {k: v for k, v in metrics.items() if k != "etapes"}

    if len(etapes) == 1:
        # Une seule étape : l'agrégation est l'identité, aucun risque d'inventer
        # un total. C'est le cas de propertyscout, nestopa, livinginsider,
        # report, verifie-backup, backup-apres-cycle et storage.
        plat.update({k: v for k, v in etapes[0].items() if k != "etape"})
    else:
        for etape in etapes:
            for cle, val in etape.items():
                if cle in ("etape", "exit"):
                    continue                    # traités séparément ci-dessous
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    if val not in (None, "", [], {}):
                        plat[cle] = val         # non comptable → dernière valeur utile
                elif cle in SOMMABLES:
                    plat[cle] = plat.get(cle, 0) + val
                else:
                    plat[cle] = val             # numérique hors liste → dernière valeur

    # `exit` = code de l'étape principale ; `then_exit` = le pire des étapes
    # chaînées. Les séparer est ce qu'exige le contrat de sortie des deux
    # extracteurs qui chaînent (fazwaz, ddproperty) : un `then` en échec ne doit
    # pas se cacher derrière un `principal` à 0.
    plat["exit"] = etapes[0].get("exit")
    codes = [e.get("exit") for e in etapes[1:] if isinstance(e.get("exit"), int)]
    if codes:
        plat["then_exit"] = max(codes, key=abs)

    plat["etapes"] = etapes
    return plat


def depuis_run(row) -> dict:
    """Métriques aplaties d'une ligne `agent_runs` du ledger (JSON illisible → {})."""
    try:
        return aplatir(json.loads(row["metrics"] or "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}

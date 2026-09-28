"""drain-tickets — referme la boucle T2 sur PC2, en fin de cycle, sans main.

Pourquoi : la routine `drain-agent-queue-lowi-bkk` vivait dans le profil PC1 et
était désactivée depuis le 2026-08-25, alors que la file est sur PC2. Relevé le
2026-09-28 : 33 tickets en attente, rien drainé depuis le 16/09.

Périmètre VOLONTAIREMENT étroit — seuls les tickets `organize /
comparaison_deleguee` sont traités ici :
  * Haiku (`claude -p`, même appel que `social-leads`) rend les SIX FAITS du
    contrat d'`organize`, jamais de verdict ;
  * `organize.appliquer_reponses()` + `decider()` tranchent, comme au retour
    d'un ticket traité à la main — le contrat ne change pas ;
  * une paire dont la réponse manque ou est mal typée est OMISE : elle reste en
    `paires-en-ticket` et ressortira (cf. organize, les deux journaux).

Les autres tickets (alertes, parser_break, fraîcheur…) exigent un jugement ou
une décision utilisateur : ils restent ouverts. On les COMPTE seulement, pour
que le rapport dise ce qui attend un humain.

INTERDIT hérité d'organize : aucune fusion, aucune suppression, aucun statut
d'annonce modifié. Ce module n'écrit que des fichiers de réponse et la file de
revue.
"""
from __future__ import annotations

import json
import os
import re
import sys

from agents.core import escalation
from agents.bots import organize
from agents.bots.social_leads import _claude_bin  # noqa: F401  (même binaire)
from agents.bots import social_leads

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPONSES = os.path.join(organize.STATE, "reponses")

# 15 paires par appel : même taille de lot que social-leads, où elle a été
# mesurée (92/92 posts extraits). Un lot de 60 = 4 appels.
LOT_APPEL = 15
# Plafond par cycle : les tickets en retard se rattrapent sur plusieurs nuits
# plutôt que d'allonger un seul cycle (le cycle finit déjà vers 07:00-09:00).
MAX_TICKETS = int(os.environ.get("DRAIN_MAX_TICKETS", 12))

SYSTEME = ("You are a strict fact extractor. You never judge or conclude. "
           "You reply with a JSON array only.")

CONSIGNES = organize.SYSTEM + """

You will receive several numbered pairs. Reply with ONE JSON array, one object
per pair, each object = {"index": <pair number>, the 6 fields}. If a pair is
unreadable, omit it. No text outside the array.

"""


def prompt_lot(paires: list[dict]) -> str:
    return CONSIGNES + "\n".join(
        f"### Pair {i}\n{p['texte']}\n" for i, p in enumerate(paires, 1))


def verite_code(p: dict) -> dict:
    """Les 6 faits recalculés en CODE depuis le texte (généré par `organize.fmt`
    à partir des champs de la base). Sert à MESURER le modèle, pas à décider :
    un écart signale une extraction fautive."""
    t = p["texte"]
    a, b = t.split("\nListing B", 1)
    def cote(s):
        prix = float(re.search(r"- ([\d,]+) THB", s).group(1).replace(",", ""))
        active = "status ACTIVE" in s
        retrait = re.search(r"delisted on (\d{4}-\d{2}-\d{2})", s)
        vu = re.search(r"first seen on (\d{4}-\d{2}-\d{2})", s)
        return prix, active, retrait.group(1) if retrait else None, vu.group(1) if vu else None
    pa, aa, ra, _ = cote(a)
    pb, ab, rb, fb = cote(b)
    return {"a_active": aa, "b_active": ab, "a_retiree": bool(ra), "b_retiree": bool(rb),
            "b_apres_a": bool(ra and fb and fb > ra),
            "ecart_prix_pct": round(abs(pa - pb) / max(pa, pb) * 100, 1) if max(pa, pb) else 0.0}


def ecarts(faits: dict, verite: dict) -> list[str]:
    out = [k for k in ("a_active", "b_active", "a_retiree", "b_retiree", "b_apres_a")
           if faits.get(k) != verite[k]]
    try:
        if abs(float(faits.get("ecart_prix_pct")) - verite["ecart_prix_pct"]) > 0.5:
            out.append("ecart_prix_pct")
    except (TypeError, ValueError):
        out.append("ecart_prix_pct")
    return out


def traiter_ticket(nom: str, appel=social_leads.appeler_claude, journal=print,
                   appliquer: bool = True) -> dict:
    sidecar = os.path.join(organize.LOTS, nom)
    with open(sidecar, encoding="utf-8") as f:
        paires = json.load(f)["paires"]
    reponses, echecs_appel, cout, faux, champs_faux = [], 0, 0.0, 0, 0
    for i in range(0, len(paires), LOT_APPEL):
        lot = paires[i:i + LOT_APPEL]
        try:
            texte, c = appel(prompt_lot(lot))
            cout += c
        except Exception as e:                                          # noqa: BLE001
            echecs_appel += 1
            journal(f"    ✗ appel Haiku : {str(e)[:200]}")
            continue
        for p, obj in zip(lot, social_leads.parser_reponse(texte, len(lot))):
            if obj is None:
                continue                      # OMISE : sera re-soumise
            faits = {k: obj.get(k) for k in organize.SCHEMA}
            e = ecarts(faits, verite_code(p))
            if e:
                faux += 1
                champs_faux += len(e)
            reponses.append({"cle": p["cle"], **faits})
    if not appliquer:                 # mesure seule : rien n'est écrit
        return {"paires": len(paires), "reponses": len(reponses), "echecs_appel": echecs_appel,
                "paires_fausses": faux, "champs_faux": champs_faux, "cout_usd": round(cout, 4)}
    os.makedirs(REPONSES, exist_ok=True)
    chemin = os.path.join(REPONSES, nom)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump({"ticket": nom, "modele": social_leads.MODELE, "reponses": reponses},
                  f, ensure_ascii=False, indent=1)
    r = organize.appliquer_reponses(chemin)
    r.update({"paires": len(paires), "echecs_appel": echecs_appel,
              "paires_fausses": faux, "champs_faux": champs_faux,
              "cout_usd": round(cout, 4)})
    return r


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    journal = lambda m: print(m, flush=True)                          # noqa: E731
    en_attente = escalation.pending()
    a_drainer = sorted(t["ticket"] for t in en_attente
                       if t.get("agent") == "organize" and t.get("kind") == "comparaison_deleguee")
    autres = [t for t in en_attente if t["ticket"] not in set(a_drainer)]

    m = {"tickets_draines": 0, "tickets_restants": 0, "paires": 0, "reponses": 0,
         "revue_ajoutee": 0, "abstentions": 0, "rejets": 0, "paires_fausses": 0,
         "echecs_appel": 0, "cout_usd": 0.0,
         "autres_tickets_ouverts": len(autres),
         "autres_par_nature": {}, "detail": []}
    for t in autres:
        k = f"{t.get('agent')}/{t.get('kind')}"
        m["autres_par_nature"][k] = m["autres_par_nature"].get(k, 0) + 1

    for nom in a_drainer[:MAX_TICKETS]:
        if not os.path.exists(os.path.join(organize.LOTS, nom)):
            journal(f"  ⚠ {nom} : lot introuvable, laissé ouvert")
            continue
        try:
            d = traiter_ticket(nom, journal=journal)
        except Exception as e:                                          # noqa: BLE001
            led.finding("drain-tickets", "medium", "drainage_echec",
                        f"{nom} : {e}", {"ticket": nom}, run_id)
            journal(f"  ✗ {nom} : {e}")
            continue
        journal(f"  ✓ {nom} : {d['reponses']}/{d['paires']} réponses, "
                f"{d['revue_ajoutee']} en revue, {d['paires_fausses']} extraction(s) fausse(s)")
        # Ticket refermé seulement si au moins une réponse est revenue : un
        # ticket tout en échec d'appel reste ouvert et sera retenté.
        if d["reponses"]:
            escalation.resolve(nom, (
                f"Drainé par drain-tickets (Haiku) : {d['reponses']}/{d['paires']} paires "
                f"constatées, {d['revue_ajoutee']} en revue, {d['abstentions']} abstentions, "
                f"{d['rejets']} rejets, {d['paires_fausses']} extractions contredites par le code."),
                ledger=led)
            m["tickets_draines"] += 1
        m["detail"].append({"ticket": nom, **{k: d[k] for k in (
            "paires", "reponses", "revue_ajoutee", "paires_fausses", "cout_usd")}})
        for k in ("paires", "reponses", "revue_ajoutee", "abstentions", "rejets",
                  "paires_fausses", "echecs_appel", "cout_usd"):
            m[k] += d[k]
    m["tickets_restants"] = max(0, len(a_drainer) - m["tickets_draines"])
    m["cout_usd"] = round(m["cout_usd"], 3)

    # Règle 2 : ne parler que si l'extraction se dégrade. Seuil : 5 % de paires
    # contredites par le code — au-delà, la file de revue se remplit de faux.
    if m["reponses"] and m["paires_fausses"] > 0.05 * m["reponses"]:
        led.finding("drain-tickets", "medium", "extraction_degradee",
                    f"{m['paires_fausses']}/{m['reponses']} extractions contredites par le code",
                    {"modele": social_leads.MODELE}, run_id)
    if m["echecs_appel"] and not m["reponses"]:
        led.finding("drain-tickets", "medium", "haiku_injoignable",
                    f"{m['echecs_appel']} appel(s) claude -p en échec, aucun ticket drainé",
                    {"modele": social_leads.MODELE}, run_id)
    return m


if __name__ == "__main__":
    class _Led:                        # rejeu manuel : findings imprimés
        def finding(self, agent, sev, kind, msg, detail=None, run_id=None):
            print(f"  [finding {sev}] {kind} : {msg}")
    if len(sys.argv) > 2 and sys.argv[1] == "--mesure":   # extraction mesurée, RIEN écrit
        print(json.dumps(traiter_ticket(sys.argv[2], appliquer=False), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run(_Led(), 0, "manuel", {}), ensure_ascii=False, indent=1))

"""organize — réconcilier sans jamais détruire.

L'arbitrage des doublons suit le MODE EXTRACTION, établi par mesure sur 100
paires réelles du dépôt :

    verdict direct   92 % de justesse, mais  0 % d'abstention
    extraction       91 % de justesse, et   77 % d'abstention

L'écart de justesse n'est pas significatif ; l'écart d'abstention est décisif.
Le modèle ne rend pas de verdict : il constate six faits, et `decider()` tranche.
L'abstention vient du code, pas du modèle — c'est pour ça qu'elle est fiable.

INTERDIT ABSOLU : aucune fusion, aucune suppression, aucun `status` modifié.
Le 2026-07-28, « 1 399 doublons exacts » s'est révélé être des lots distincts
versés en lot par une agence. Une dédup aurait effacé de l'offre réelle.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

from agents.core import db, escalation, local_llm
from agents.core import gpu

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "organize")
REVUE = os.path.join(STATE, "revue.jsonl")

# Plafond par cycle : 28 000 paires ambiguës × 3,6 s ≈ 28 h. On traite par lots.
LOT_MAX = 300

# ───────────────────────── mode « T1 absent » ─────────────────────────
# Le 2e poste (24/7) ne peut pas héberger Ollama. La comparaison part alors en
# TICKET, drainé par la routine `drain-agent-queue-lowi-bkk` (quotidienne).
#
# Lot volontairement petit — 60 et non 300. Ce n'est plus le débit du GPU qui
# borne, c'est ce qu'une session de revue traite d'un coup sans se dégrader.
# Le rendement mesuré ne réclame d'ailleurs pas 300 : sur les 5 runs aboutis du
# 2026-07-31 au 2026-08-17, 980 paires soumises au modèle local ont produit
# SEPT entrées de revue. Le goulot n'est pas le volume soumis.
TICKET_LOT = 60

# DEUX journaux distincts, et c'est le point délicat.
#   paires-faites.txt   → paire TRANCHÉE, ne jamais retirer
#   paires-en-ticket.txt → paire SOUMISE, réponse en attente
# Les confondre reproduirait le défaut du 2026-08-17 : des paires marquées
# « traitées » alors qu'elles avaient échoué, donc jamais re-tirées. Une paire
# déposée n'entre dans `paires-faites` qu'au retour effectif de sa réponse.
EN_TICKET = os.path.join(STATE, "paires-en-ticket.txt")
FAITES = os.path.join(STATE, "paires-faites.txt")
LOTS = os.path.join(STATE, "lots")

# PROMPT EN ANGLAIS — mesuré le 2026-08-01 sur 90 paires ambiguës réelles, en
# ciblant la configuration qui échoue (A sans date de retrait, B retirée) :
#
#     consignes en français ... 12,2 % d'extractions internement incohérentes
#     mêmes consignes traduites  0,0 %
#
# La cause est la LANGUE, pas le nommage des champs : la variante anglaise garde
# les mêmes noms opaques (`b_apres_a`) et tombe déjà à zéro. qwen3 est entraîné
# majoritairement sur de l'anglais ; lui demander une sortie structurée stricte
# en français dégrade sa tenue des contraintes.
#
# Les noms de champs restent en français : ils sont lus par du code français, et
# la mesure montre qu'ils n'ont aucun effet sur la fiabilité.
SYSTEM = """You READ two property listings and REPORT FACTS. Do not judge, do not conclude.

Fill exactly these fields, based only on the text provided:
  a_active   : true if listing A has status ACTIVE, else false
  b_active   : true if listing B has status ACTIVE, else false
  a_retiree  : true if listing A has a delisting date, else false
  b_retiree  : true if listing B has a delisting date, else false
  b_apres_a  : true if B was first seen AFTER A's delisting date
               (false if A has no delisting date)
  ecart_prix_pct : price gap between A and B, as a percentage of the larger, 1 decimal

Reply ONLY with JSON containing these 6 fields. No other field, no comment."""

SCHEMA = {"a_active": "bool", "b_active": "bool", "a_retiree": "bool",
          "b_retiree": "bool", "b_apres_a": "bool", "ecart_prix_pct": "number"}

# Paires candidates : même immeuble normalisé, khet, chambres, surface, deal_type, source.
SQL_PAIRES = """
with n as (
  select id, source, deal_type, status, price, area_sqm, bedrooms, khet, condo_name,
         first_seen, delisted_at, agent_id,
         lower(regexp_replace(coalesce(condo_name,''), '[^a-zA-Z0-9]', '', 'g')) as ckey
  from listings
  where condo_name is not null and area_sqm is not null
    and bedrooms is not null and price > 0
),
p as (
  select a.id ida, b.id idb, a.source, a.deal_type, a.condo_name, a.khet, a.bedrooms,
         a.area_sqm sa, b.area_sqm sb, a.price pa, b.price pb,
         a.status sta, b.status stb, a.first_seen fsa, b.first_seen fsb,
         a.delisted_at da, b.delisted_at db, a.agent_id aga, b.agent_id agb,
         abs(a.price - b.price) / greatest(a.price, b.price)::float as ecart_prix,
         (a.status = 'active' and b.status = 'active') as deux_actives,
         (a.delisted_at is not null and b.first_seen > a.delisted_at
            and b.first_seen - a.delisted_at < interval '90 days') as sequentiel
  from n a join n b
    on a.ckey = b.ckey and a.khet = b.khet and a.bedrooms = b.bedrooms
   and a.deal_type = b.deal_type and a.source = b.source
   and abs(a.area_sqm - b.area_sqm) < 0.01 and a.id < b.id
)
select * from p
"""


# ───────────────────── mise en forme et décision ─────────────────────
def _d(x) -> str:
    return str(x)[:10] if x else ""


def fmt(p: dict) -> str:
    """Mise en forme EN ANGLAIS — cf. le commentaire de SYSTEM. Les valeurs
    (nom d'immeuble, quartier, deal_type) sont déjà anglaises en base : tout
    présenter dans la même langue retire la dernière source de confusion."""
    def side(tag: str, i: str) -> str:
        st = p[f"st{i}"]
        statut = "ACTIVE" if st == "active" else f"{st.upper()} (delisted on {_d(p['d' + i])})"
        ag = p[f"ag{i}"]
        return (f"Listing {tag} : {p['condo_name']} - {p['khet']} - {p['bedrooms']} bed - "
                f"{float(p['s' + i]):.2f} sqm - {float(p['p' + i]):,.0f} THB ({p['deal_type']})"
                f"{f', agent={ag}' if ag else ''}\n"
                f"  first seen on {_d(p['fs' + i])} - status {statut}")
    return side("A", "a") + "\n" + side("B", "b")


def prefiltre_sql(p: dict) -> str | None:
    """Ce que le SQL tranche seul — gratuitement et sans erreur.
    Ne JAMAIS soumettre au modèle une paire que cette fonction tranche."""
    if p["deux_actives"]:
        return "distinct_units"
    if p["sequentiel"] and p["ecart_prix"] < 0.02:
        return "same_unit"
    return None


def coherent(faits: dict) -> bool:
    """Le modèle se contredit-il ?

    Relevé le 2026-08-01 sur 25 paires réelles : dans 9 cas, le modèle rendait
    `a_retiree=False` ET `b_apres_a=True` — logiquement impossible, la consigne
    dit « false si A n'a pas de date de retrait ». Là où l'écart de prix était
    nul, cette contradiction produisait un FAUX `same_unit` (cas #6 et #10).

    Une incohérence interne est détectable sans rien savoir du marché : c'est
    au code de la refuser, pas au prompt de l'éviter."""
    if faits.get("b_apres_a") and not faits.get("a_retiree"):
        return False          # B ne peut pas suivre un retrait qui n'existe pas
    if faits.get("a_active") and faits.get("a_retiree"):
        return False          # active ET retirée
    if faits.get("b_active") and faits.get("b_retiree"):
        return False
    return True


def decider(faits: dict, dates: dict | None = None) -> str:
    """La décision appartient au CODE. C'est d'ici que vient l'abstention.

    `dates` (optionnel) porte les dates RÉELLES de la base. Quand elles sont
    fournies, la chronologie est recalculée ici plutôt que lue chez le modèle :
    comparer deux dates est précisément ce que le code fait parfaitement et ce
    qu'un modèle de 8 milliards de paramètres rate (cas #21 — B vue le 02/07,
    A retirée le 16/07, et le modèle affirmait pourtant b_apres_a=true)."""
    if not coherent(faits):
        return "insufficient"
    if faits["a_active"] and faits["b_active"]:
        return "distinct_units"

    b_apres_a = faits["b_apres_a"]
    if dates:
        da, fsb = dates.get("da"), dates.get("fsb")
        b_apres_a = bool(da and fsb and fsb > da)

    if b_apres_a and faits["ecart_prix_pct"] < 2.0:
        return "same_unit"
    return "insufficient"


# ───────────────────── contrôles déterministes ─────────────────────
BORNES_TS = os.path.join(os.path.dirname(ROOT), "lib", "market-bounds.ts")


_CONST_TS = re.compile(r"export\s+const\s+(\w+)\s*=\s*([\d_]+)")


def _bornes_ts() -> dict[str, int]:
    """Constantes de lib/market-bounds.ts. Les valeurs y sont écrites avec des
    séparateurs numériques (`800_000`) — les lire comme du texte brut ne marche pas."""
    if not os.path.exists(BORNES_TS):
        return {}
    src = open(BORNES_TS, encoding="utf-8").read()
    return {nom: int(val.replace("_", "")) for nom, val in _CONST_TS.findall(src)}


def _bornes_sql() -> dict[str, int]:
    """Bornes réellement appliquées par la vue `listings_sane`, lues dans sa
    définition. On compare au code SQL en production, pas au fichier de migration
    — c'est la vue qui filtre les statistiques."""
    try:
        d = db.scalar("select pg_get_viewdef('listings_sane'::regclass, true)")
    except Exception:  # noqa: BLE001
        return {}
    if not d:
        return {}
    out: dict[str, int] = {}
    if (m := re.search(r"area_sqm\s*>=\s*(\d+)", d)):
        out["AREA_MIN"] = int(m.group(1))
    if (m := re.search(r"area_sqm\s*<=\s*(\d+)", d)):
        out["AREA_MAX"] = int(m.group(1))
    if (m := re.search(r"'sale'.*?price\s*>=\s*(\d+).*?price\s*<=\s*(\d+)", d, re.S)):
        out["SALE_MIN"], out["SALE_MAX"] = int(m.group(1)), int(m.group(2))
    if (m := re.search(r"'rent'.*?price\s*>=\s*(\d+).*?price\s*<=\s*(\d+)", d, re.S)):
        out["RENT_MIN"], out["RENT_MAX"] = int(m.group(1)), int(m.group(2))
    return out


def verifier_bornes(led, run_id: int) -> bool:
    """`lib/market-bounds.ts` et la vue `listings_sane` doivent dire la MÊME chose.

    Un écart entre les deux fausse silencieusement toute statistique : le tableau
    web filtrerait sur une borne, les médianes SQL sur une autre. C'est le défaut
    corrigé le 2026-07-28, et rien n'empêchait qu'il revienne."""
    ts, sql = _bornes_ts(), _bornes_sql()
    if not ts:
        led.finding("organize", "high", "bornes_absentes",
                    "lib/market-bounds.ts introuvable ou illisible", {}, run_id)
        return False
    if not sql:
        led.finding("organize", "medium", "bornes_sql_illisible",
                    "Définition de listings_sane non relue — comparaison impossible",
                    {"ts": ts}, run_id)
        return False

    ecarts = {k: {"ts": ts.get(k), "sql": v} for k, v in sql.items() if ts.get(k) != v}
    if ecarts:
        led.finding("organize", "high", "bornes_divergentes",
                    f"TS et listings_sane divergent sur : {', '.join(sorted(ecarts))}",
                    {"ecarts": ecarts}, run_id)
        return False
    return True


# ───────────────── délégation à Claude quand T1 est absent ─────────────────
def _purger_en_ticket() -> int:
    """Rend tirables les paires d'un ticket drainé qui n'ont jamais reçu de réponse.

    Sans ça, une paire déposée dans un ticket clos sans réponse resterait à
    jamais dans `paires-en-ticket` sans jamais entrer dans `paires-faites` :
    elle disparaîtrait du tirage en silence. Rend le nombre de paires libérées."""
    if not os.path.exists(EN_TICKET) or not os.path.isdir(LOTS):
        return 0
    en_attente = {t.get("ticket") for t in escalation.pending()}
    encore = set()
    for nom in os.listdir(LOTS):
        if nom not in en_attente:
            continue
        try:
            with open(os.path.join(LOTS, nom), encoding="utf-8") as f:
                encore |= {p["cle"] for p in json.load(f).get("paires", [])}
        except (json.JSONDecodeError, KeyError, OSError):
            continue

    with open(EN_TICKET, encoding="utf-8") as f:
        avant = {l.strip() for l in f if l.strip()}
    garde = avant & encore
    if len(garde) == len(avant):
        return 0
    tmp = EN_TICKET + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("".join(f"{c}\n" for c in sorted(garde)))
    os.replace(tmp, EN_TICKET)      # remplacement atomique : jamais de fichier à moitié écrit
    return len(avant) - len(garde)


def deposer_en_ticket(led, run_id: int, ambigues: list[dict]) -> dict:
    """Dépose un lot de paires en ticket au lieu de l'envoyer au modèle local.

    Le contrat NE CHANGE PAS : on demande les six mêmes faits, et c'est
    `decider()` qui tranche au retour. C'est de là que vient l'abstention — la
    mesure du 2026-07-31 est formelle, le verdict direct atteint 92 % mais ne
    s'abstient JAMAIS (0/30 sur les cas indécidables). Déléguer la comparaison
    ne doit pas devenir déléguer la DÉCISION."""
    os.makedirs(LOTS, exist_ok=True)
    taille = int(os.environ.get("ORGANIZE_TICKET_LOT", TICKET_LOT))
    liberees = _purger_en_ticket()

    with gpu.Reprise(FAITES) as faites, gpu.Reprise(EN_TICKET) as deposees:
        lot = []
        for p in ambigues:
            cle = f"{p['ida']}|{p['idb']}"
            if cle in faites or cle in deposees:
                continue
            lot.append((cle, p))
            if len(lot) >= taille:
                break

        if not lot:
            return {"mode": "tickets", "paires_deposees": 0, "ticket": None,
                    "paires_liberees": liberees,
                    "note": "rien de nouveau à soumettre"}

        paires = [{
            "cle": cle,
            "ida": p["ida"], "idb": p["idb"], "source": p["source"],
            "condo": p["condo_name"], "khet": p["khet"],
            "texte": fmt(p),
            # Dates RÉELLES : `decider()` recalcule la chronologie en code au
            # retour. Cas #21 — B vue le 02/07, A retirée le 16/07, et un modèle
            # affirmait pourtant b_apres_a=true.
            "dates": {"da": str(p.get("da") or ""), "fsb": str(p.get("fsb") or "")},
        } for cle, p in lot]

        ticket = escalation.create(
            agent="organize", kind="comparaison_deleguee", severity="low",
            subject=f"{len(paires)} paires ambiguës à comparer (poste sans modèle local)",
            evidence={"paires": paires, "schema_attendu": SCHEMA,
                      "consigne_extraction": SYSTEM,
                      "reste_ambigues": len(ambigues)},
            asked_of_claude=(
                "CONSTATER, PAS CONCLURE. Pour chaque paire, rendre les 6 champs de "
                "`schema_attendu` en lisant `texte` — rien d'autre. Ne PAS rendre de "
                "verdict : c'est `decider()` qui tranche au retour, et c'est de là que "
                "vient l'abstention (mesuré : verdict direct 92 % de justesse mais 0 % "
                "d'abstention ; extraction 91 % et 77 % d'abstention).\n"
                "Écrire les réponses dans agents/state/organize/reponses/<ticket>.json :\n"
                '  {"ticket": "<nom du ticket>", "reponses": [{"cle": "<cle>", '
                '"a_active": bool, "b_active": bool, "a_retiree": bool, "b_retiree": bool, '
                '"b_apres_a": bool, "ecart_prix_pct": number}, ...]}\n'
                "Puis appliquer :\n"
                "  scraper/.venv/Scripts/python.exe -m agents.bots.organize "
                "--appliquer agents/state/organize/reponses/<ticket>.json\n"
                "Une paire dont on ne sait rien : l'OMETTRE. Elle sera re-soumise. "
                "Ne jamais inventer un fait pour compléter le lot."),
            ledger=led)

        # Sidecar : la copie du lot survit au déplacement du ticket vers
        # queue/done/. Sans elle, appliquer une réponse après drainage
        # perdrait les dates réelles, donc la chronologie.
        with open(os.path.join(LOTS, ticket), "w", encoding="utf-8") as f:
            json.dump({"ticket": ticket, "paires": paires}, f,
                      ensure_ascii=False, indent=1)

        for cle, _ in lot:
            deposees.marquer(cle)

    return {"mode": "tickets", "paires_deposees": len(paires), "ticket": ticket,
            "paires_liberees": liberees}


def appliquer_reponses(chemin: str) -> dict:
    """Referme la boucle : réponses → `decider()` → file de revue.

    Sans ce chemin de retour, le dépôt de tickets serait un mécanisme à moitié
    câblé — exactement ce que le journal reproche au T2 promis le 2026-07-31 et
    que rien ne drainait avant le 2026-08-05."""
    with open(chemin, encoding="utf-8") as f:
        rep = json.load(f)
    ticket = rep.get("ticket") or os.path.basename(chemin)

    sidecar = os.path.join(LOTS, ticket)
    if not os.path.exists(sidecar):
        raise SystemExit(f"Lot introuvable pour ce ticket : {sidecar}")
    with open(sidecar, encoding="utf-8") as f:
        lot = {p["cle"]: p for p in json.load(f)["paires"]}

    abstentions, revue, rejets = 0, 0, 0
    os.makedirs(STATE, exist_ok=True)
    with gpu.Reprise(FAITES) as faites, open(REVUE, "a", encoding="utf-8") as fh:
        for r in rep.get("reponses", []):
            cle = r.get("cle")
            p = lot.get(cle)
            if p is None:
                rejets += 1
                continue
            faits = {k: r.get(k) for k in SCHEMA}
            try:
                # Même validation que pour le modèle local : un champ manquant
                # ou d'un type faux est REJETÉ, jamais complété par défaut.
                faits = local_llm.validate(faits, SCHEMA)
            except local_llm.LLMError:
                rejets += 1
                continue

            verdict = decider(faits, p.get("dates"))
            if verdict == "insufficient":
                abstentions += 1
            else:
                fh.write(json.dumps({
                    "ida": p["ida"], "idb": p["idb"], "source": p["source"],
                    "condo": p["condo"], "khet": p["khet"],
                    "verdict_modele": verdict, "faits": faits,
                    "origine": f"ticket:{ticket}",
                    "statut_revue": "en_attente",
                }, ensure_ascii=False, default=str) + "\n")
                fh.flush()
                revue += 1
            # TRANCHÉE seulement maintenant. Une paire absente du fichier de
            # réponses ou rejetée reste en `paires-en-ticket` sans entrer ici :
            # elle ressortira au prochain nettoyage, elle n'est pas perdue.
            faites.marquer(cle)

    return {"ticket": ticket, "reponses": len(rep.get("reponses", [])),
            "abstentions": abstentions, "revue_ajoutee": revue, "rejets": rejets}


# ───────────────────── point d'entrée ─────────────────────
def run(led, run_id: int, lane: str, spec: dict) -> dict:
    os.makedirs(STATE, exist_ok=True)
    bornes_ok = verifier_bornes(led, run_id)

    paires = db.query(SQL_PAIRES)
    tranchees_sql, ambigues = 0, []
    for p in paires:
        if prefiltre_sql(p) is not None:
            tranchees_sql += 1
        else:
            ambigues.append(p)

    # Traitement par lots : le stock complet représenterait ~28 h en flux unique.
    # TIRAGE ALÉATOIRE, pas la tête de liste.
    #
    # `ambigues[:300]` prenait les 300 premières d'une requête SANS `order by` :
    # une tranche arbitraire, en pratique groupée par immeuble et par source,
    # donc structurellement homogène. Mesuré le 2026-08-11 : cette tranche rendait
    # 9 % d'abstention, quand un tirage aléatoire sur la MÊME population en donne
    # 97 %. On ne mesurait pas le modèle, on mesurait un coin de la base.
    #
    # S'y ajoutait un défaut plus grave : sans mémoire des paires déjà vues, le
    # même lot repassait à chaque cycle et les 25 848 autres n'auraient jamais
    # été traitées. Le journal de reprise (`gpu.Reprise`) l'a corrigé le même jour.
    random.shuffle(ambigues)

    # Poste sans modèle local : on dépose, on ne compare pas ici. Le tirage
    # aléatoire ci-dessus vaut pour les deux modes — c'est lui qui garantit que
    # l'échantillon soumis représente la population, pas un coin de la base.
    if local_llm.t1_absent():
        m = deposer_en_ticket(led, run_id, ambigues)
        m.update({"backfills": 0, "bornes_alignees": bornes_ok,
                  "paires_candidates": len(paires), "paires_sql": tranchees_sql,
                  "reste_ambigues": len(ambigues) - m["paires_deposees"]})
        return m

    lot = ambigues[:int(os.environ.get("ORGANIZE_LOT", LOT_MAX))]
    abstentions, pannes, revue = 0, 0, 0
    t0 = time.time()

    # Instance unique : le 2026-08-02, deux exemplaires du même traitement se
    # sont disputé le GPU treize minutes sans que rien ne le signale.
    # `Reprise` note chaque paire tranchée : une coupure ne fait pas repartir de
    # zéro, et l'utilisateur peut reprendre sa machine quand il veut.
    reprise = gpu.Reprise(FAITES)
    cessions = 0
    with gpu.Verrou("organize"), reprise, open(REVUE, "a", encoding="utf-8") as fh:
        for i, p in enumerate(lot, 1):
            cle = f"{p['ida']}|{p['idb']}"
            if cle in reprise:
                continue
            # Céder la carte AVANT d'appeler : le modèle pèse ~5 Go sur 8 Go de
            # VRAM. S'il ne rentre plus, il déborde sur le CPU — les réponses
            # restent justes, seul le débit s'effondre. Panne muette.
            if not gpu.gpu_libre()[0]:
                cessions += 1
            gpu.ceder_si_besoin(journal=lambda m: print(f"  {m}", flush=True))
            faits = local_llm.ask_safe(
                SYSTEM, fmt(p), SCHEMA, ledger=led, agent="organize",
                run_id=run_id, num_predict=300)
            if faits is None:
                pannes += 1
            else:
                # On passe les dates RÉELLES : la chronologie se tranche en code.
                verdict = decider(faits, {"da": p.get("da"), "fsb": p.get("fsb")})
                if verdict == "insufficient":
                    abstentions += 1
                else:
                    # Verdict non abstenu → FILE DE REVUE.
                    # Aucun effet sur les statistiques de marché.
                    fh.write(json.dumps({
                        "ida": p["ida"], "idb": p["idb"], "source": p["source"],
                        "condo": p["condo_name"], "khet": p["khet"],
                        "verdict_modele": verdict, "faits": faits,
                        "statut_revue": "en_attente",
                    }, ensure_ascii=False, default=str) + "\n")
                    fh.flush()   # sinon rien n'atteint le disque avant la fin du lot
                    revue += 1
            reprise.marquer(cle)
            # Progression : un lot de 300 dure ~20 min. Sans trace, impossible de
            # distinguer « en cours » de « bloqué ».
            if i % 25 == 0 or i == len(lot):
                ecoule = time.time() - t0
                print(f"  organize {i}/{len(lot)} — {abstentions} abstentions, "
                      f"{revue} en revue, {pannes} pannes "
                      f"({ecoule / i:.1f} s/paire)", flush=True)

    traites = len(lot) - pannes
    taux = abstentions / traites if traites else 1.0

    # Garde-fou mesuré : en dessous de 70 % d'abstention, le modèle invente.
    if traites >= 30 and taux < 0.70:
        led.finding("organize", "high", "modele_derive",
                    f"Abstention tombée à {taux:.0%} (seuil 70 %) — le modèle "
                    f"invente des certitudes sur des cas indécidables",
                    {"abstentions": abstentions, "traites": traites}, run_id)
        escalation.create(
            agent="organize", kind="modele_derive", severity="high",
            subject=f"Taux d'abstention à {taux:.0%}, sous le seuil de 70 %",
            evidence={"abstentions": abstentions, "traites": traites,
                      "reference_mesuree": "77 % sur 30 paires ambiguës (2026-07-31)"},
            asked_of_claude="Vérifier le prompt d'extraction et le schéma de sortie "
                            "d'agents/bots/organize.py. Ne PAS relâcher le seuil sans "
                            "refaire la mesure sur agents/tests/pairs.json.",
            ledger=led)

    return {"backfills": 0, "bornes_alignees": bornes_ok,
            "paires_candidates": len(paires), "paires_sql": tranchees_sql,
            "paires_modele": traites, "abstentions": abstentions,
            "taux_abstention": round(taux, 3), "revue_ajoutee": revue,
            "pannes_llm": pannes, "reste_ambigues": len(ambigues) - len(lot)}


# ───────────────────── application des réponses déléguées ─────────────────────
# Appelé par la session Claude qui draine `agents/queue/`. Volontairement un
# point d'entrée séparé : appliquer une réponse ne doit JAMAIS pouvoir relancer
# un scan ni toucher à la base des annonces.
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="organize — application des réponses déléguées")
    ap.add_argument("--appliquer", metavar="FICHIER",
                    help="fichier de réponses JSON produit pour un ticket")
    a = ap.parse_args()
    if not a.appliquer:
        ap.error("rien à faire : préciser --appliquer <fichier>")
    print(json.dumps(appliquer_reponses(a.appliquer), ensure_ascii=False, indent=2))

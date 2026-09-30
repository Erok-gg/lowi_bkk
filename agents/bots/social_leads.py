"""social_leads.py — de la collecte Facebook brute à la table social_leads, sans main.

POURQUOI CET AGENT EXISTE (2026-09-13). Le collecteur `scraper/social/`
écrivait chaque nuit `scraper/output/social/immo_YYYY-MM-DD.json` (≈ 90 posts)
et rien ne les lisait : la « routine Claude/Haiku planifiée » annoncée le
2026-09-12 n'avait jamais été créée. L'aval (extraction structurée →
rapprochement avec les condos Lowi → chargement) restait trois commandes à la
main, donc jamais lancées.

TROIS ÉTAPES, TROIS RESPONSABLES :
  1. EXTRACTION — un modèle lit le texte libre thaï/anglais et remplit un
     schéma. PC2 n'a pas d'Ollama (marqueur `agents/t1-absent`) ; on appelle
     **Claude en ligne de commande** (`claude -p`, Haiku), présent sur le poste
     depuis la migration du 2026-08-21. Mesuré le 2026-09-13 : un appel à
     contexte minimal (`--tools ""`, `--setting-sources ""`, prompt système
     propre) coûte ~48 k tokens de mise en cache la première fois, puis lit
     le cache ; d'où des LOTS de posts par appel, pas un appel par post comme
     avec Ollama. Le prompt et le schéma sont ceux de `immo-extract.mjs`, à
     l'identique — c'est l'exécutant qui change, pas le contrat.
  2. DÉCISION PAR LE CODE sur `vendeur` et `quota` (marqueurs textuels nets,
     le modèle inventait un propriétaire par défaut) — port exact des regex
     de `immo-extract.mjs`.
  3. RAPPROCHEMENT (`node immo-resolve.mjs`) puis CHARGEMENT
     (`load_social_leads.py --sqlite`, base `social-leads.db` séparée de la
     référence, décision du 2026-09-12) — inchangés, appelés tels quels.

CE QUI EST TRAITÉ : tout `immo_*.json` sans `_charge.json` à côté — ce
marqueur n'est écrit qu'APRÈS le chargement en base. L'existence des
fichiers dérivés EST l'état, pas un journal séparé qui pourrait diverger.
Trouvé au premier run (2026-09-13) : `_extrait_resolu.json` comme marqueur
ne suffisait pas — un `immo-resolve` lancé à la main l'avait produit, et
l'agent tenait le fichier pour traité sans que rien ne soit en base. Un fichier dont l'extraction a échoué en partie est
quand même écrit (les posts en échec sont comptés, pas rejoués : la même
annonce revient dans les 7 jours de fenêtre du collecteur).

GARDE-FOU : si le dernier `immo_*.json` a plus de 48 h, la collecte est
muette — c'est exactement ce que l'audit du 2026-09-13 a trouvé (tâche en
0x1 chaque nuit, personne ne le voyait). Finding medium, pas de mail.

Rejeu manuel :  scraper/.venv/Scripts/python.exe -m agents.bots.social_leads [fichier.json]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOCIAL = ROOT / "scraper" / "social"
OUT = ROOT / "scraper" / "output" / "social"
PY = ROOT / "scraper" / ".venv" / "Scripts" / "python.exe"
LOADER = ROOT / "scraper" / "load_social_leads.py"

MODELE = "claude-haiku-4-5-20251001"
LOT = 15                 # posts par appel : assez pour amortir le contexte, pas
                         # assez pour que le modèle mélange deux annonces
COLLECTE_MUETTE_H = 48

CHAMPS = ["est_une_annonce", "type_transaction", "type_bien", "prix_vente_thb",
          "loyer_mensuel_thb", "surface_sqm", "chambres", "salles_de_bain",
          "nom_immeuble", "station_proche", "quartier", "meuble", "vendeur",
          "quota", "confiance"]

# ─── Décision côté CODE (port de immo-extract.mjs, à garder alignés) ────────
MARQ_PROPRIO = re.compile(r"เจ้าของ|owner\s*(post|direct)?|by\s*owner|ไม่ผ่านนายหน้า|no\s*agent|direct\s*from\s*owner", re.I)
MARQ_AGENT = re.compile(r"\b(agent|agency|realty|real\s*estate|property|properties|estate|homes|broker)\b|นายหน้า|บริษัท", re.I)
MARQ_QUOTA_ETR = re.compile(r"โควต[า้]?\s*ต่างชาติ|foreign(er)?\s*quota|foreign\s*(free\s*hold|freehold)|farang\s*quota|quota\s*ét?ranger", re.I)
MARQ_QUOTA_THAI = re.compile(r"โควต[า้]?\s*ไทย|thai\s*quota|thai\s*name|ชื่อคนไทย", re.I)


def deduire_quota(post: dict) -> str:
    t = f"{post.get('author') or ''} {post.get('content') or ''}"
    if MARQ_QUOTA_ETR.search(t):
        return "etranger"
    if MARQ_QUOTA_THAI.search(t):
        return "thai"
    return "inconnu"      # sans marqueur on n'invente pas


def deduire_vendeur(post: dict, valeur_modele: str) -> str:
    auteur, texte = post.get("author") or "", post.get("content") or ""
    if MARQ_AGENT.search(auteur):
        return "agent"
    if MARQ_PROPRIO.search(texte):
        return "proprietaire"
    if MARQ_AGENT.search(texte):
        return "agent"
    return "inconnu" if valeur_modele == "proprietaire" else (valeur_modele or "inconnu")


# ─── Prompt (immo-extract.mjs, adapté au lot) ───────────────────────────────
SYSTEME = "Tu es un extracteur de données. Tu réponds UNIQUEMENT par du JSON valide, sans commentaire."

CONSIGNES = """Tu extrais les données d'annonces immobilières publiées dans des groupes Facebook de Bangkok. Les textes sont en thaï, en anglais ou les deux, souvent incomplets et mal structurés.

RÈGLES DE CONVERSION DES MONTANTS — tous les prix sont en bahts thaïlandais (THB), à convertir en ENTIER :
- "13.5 ล้าน" ou "13.5 million" ou "13.5M" = 13500000
- "60K" ou "60k" = 60000
- "18,000" = 18000
- "98,000บาท/เดือน" = loyer mensuel de 98000
- Un prix de VENTE est en millions ; un LOYER est en milliers par mois. Si un montant de 15 000 est annoncé sans précision, c'est un loyer mensuel.

VOCABULAIRE THAÏ UTILE :
- ขาย = vendre / à vendre · ให้เช่า ou เช่า = à louer · ขายหรือให้เช่า = vente OU location
- ราคาขาย = prix de vente · ราคาเช่า = prix de location · บาท = baht · เดือน = mois
- ห้องนอน = chambre · ห้องน้ำ = salle de bain · ตรม. ou ตร.ม. = m²
- เจ้าของขายเอง ou เจ้าของ = par le propriétaire directement
- คอนโด = condo · บ้านเดี่ยว = maison individuelle · ทาวน์เฮาส์ = townhouse
- โครงการ = nom du projet/résidence · ต้องการหา = recherche (demande, pas une offre)
- โควตาต่างชาติ ou โควต้าต่างชาติ = quota ÉTRANGER (foreign quota) · โควตาไทย = quota thaï

CONSIGNES :
- "est_une_annonce" est faux si le texte ne propose ni ne cherche un bien (discussion, publicité de service, question générale).
- "type_transaction" : par défaut une annonce est une OFFRE. Dès qu'un bien est DÉCRIT (nom d'immeuble, surface, prix, "For Rent", "ให้เช่า", "ขาย"), c'est "location" ou "vente" — JAMAIS "recherche", même si l'annonce est courte ou tronquée. N'utilise "recherche" QUE si l'auteur cherche un logement POUR LUI : "looking for", "I need a condo", "ต้องการหา", "budget around 20k", "wanted".
- "nom_immeuble" : recopie le nom du projet tel qu'écrit, sans traduire. "" si absent.
- "station_proche" : la station BTS/MRT citée (ex. "BTS Ekkamai"). "" si absente.
- "quota" : "etranger" si l'annonce mentionne un quota étranger ; "thai" si elle précise un quota thaï ; "inconnu" dans TOUS les autres cas.
- N'INVENTE JAMAIS une valeur absente : mets 0 pour un nombre, "" pour un texte. Une annonce tronquée est normale.
- "confiance" : 5 = tout est explicite ; 1 = texte très pauvre ou ambigu.

SCHÉMA de chaque objet (toutes les clés obligatoires) :
{"index": entier (numéro de l'annonce ci-dessous), "est_une_annonce": bool, "type_transaction": "vente"|"location"|"vente_et_location"|"recherche"|"autre", "type_bien": "condo"|"maison"|"townhouse"|"terrain"|"commerce"|"inconnu", "prix_vente_thb": entier, "loyer_mensuel_thb": entier, "surface_sqm": entier, "chambres": entier, "salles_de_bain": entier, "nom_immeuble": texte, "station_proche": texte, "quartier": texte, "meuble": bool, "vendeur": "proprietaire"|"agent"|"inconnu", "quota": "etranger"|"thai"|"inconnu", "confiance": 1-5}

Réponds par un TABLEAU JSON contenant exactement un objet par annonce, dans l'ordre, sans texte autour.

ANNONCES :
"""


def prompt_lot(posts: list[dict]) -> str:
    blocs = []
    for i, p in enumerate(posts, 1):
        texte = (p.get("content") or "").strip()[:2500]
        blocs.append(f"### Annonce {i}\n{texte}\n")
    return CONSIGNES + "\n".join(blocs)


# ─── Appel du modèle ────────────────────────────────────────────────────────
class AuthClaudeExpiree(RuntimeError):
    """Le CLI n'est plus authentifié : aucun lot ne peut réussir, et seul
    l'utilisateur peut y remédier (`claude` puis /login — pas de mot de passe
    saisi par un agent). Distincte d'un échec de lot pour arrêter tout de
    suite au lieu de brûler un appel par lot et par fichier."""


EST_AUTH = re.compile(r"Failed to authenticate|OAuth|not logged in|/login|Invalid API key", re.I)


def _claude_bin() -> str:
    c = shutil.which("claude") or shutil.which("claude.exe")
    if not c:
        c = str(Path.home() / ".local" / "bin" / "claude.exe")
    return c


def appeler_claude(prompt: str, timeout: int = 300) -> tuple[str, float]:
    """Rend (texte de réponse, coût USD annoncé). Lève en cas d'échec.

    cwd = dossier temporaire : sans ça le CLI charge CLAUDE.md et les
    réglages du dépôt (mesuré : 64 k tokens de contexte contre 48 k)."""
    cmd = [_claude_bin(), "-p", "--model", MODELE, "--output-format", "json",
           "--tools", "", "--setting-sources", "", "--system-prompt", SYSTEME]
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, cwd=tmp)
    # La cause est dans le champ `result` du JSON, qui arrive EN FIN de sortie :
    # tronquer stdout à 300 caractères la coupait. Mesuré le 2026-09-30 :
    # 162 appels en échec du 23 au 29/09, tous journalisés sans leur cause
    # (« OAuth session expired »), et l'alerte disait « le modèle n'a rien
    # rendu d'exploitable » — une panne d'authentification déguisée en
    # défaut de modèle pendant 7 jours.
    try:
        d = json.loads(r.stdout)
    except (json.JSONDecodeError, TypeError):
        d = None
    cause = str(d.get("result"))[:300] if isinstance(d, dict) else (r.stderr or r.stdout)[:300]
    if r.returncode != 0 or not isinstance(d, dict) or d.get("is_error"):
        if EST_AUTH.search(cause):
            raise AuthClaudeExpiree(cause)
        raise RuntimeError(f"claude -p code {r.returncode} : {cause}")
    return d.get("result") or "", float(d.get("total_cost_usd") or 0)


def parser_reponse(texte: str, attendu: int) -> list[dict | None]:
    """Tableau JSON (fences tolérées) → liste indexée par position, None si
    un objet manque ou est inexploitable. Jamais d'exception : un lot mal
    formé compte des échecs, il ne fait pas tomber l'agent."""
    m = re.search(r"\[.*\]", texte, re.S)
    if not m:
        return [None] * attendu
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return [None] * attendu
    if not isinstance(data, list):
        return [None] * attendu
    par_index: dict[int, dict] = {}
    for k, obj in enumerate(data):
        if not isinstance(obj, dict):
            continue
        idx = obj.get("index")
        idx = int(idx) if isinstance(idx, (int, float)) and 1 <= idx <= attendu else k + 1
        par_index.setdefault(idx, obj)
    return [par_index.get(i) for i in range(1, attendu + 1)]


def normaliser(obj: dict, post: dict) -> dict:
    """Types forcés (le modèle rend parfois "13.5M" ou null), décisions du
    code appliquées, champs de provenance ajoutés — même format que
    immo-extract.mjs, pour que immo-resolve et load_social_leads ne voient
    aucune différence."""
    def ent(v):
        if isinstance(v, bool):
            return 0
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = re.sub(r"[^\d.]", "", v)
            try:
                return int(float(s)) if s else 0
            except ValueError:
                return 0
        return 0
    d = {
        "est_une_annonce": bool(obj.get("est_une_annonce")),
        "type_transaction": obj.get("type_transaction") if obj.get("type_transaction") in
                            ("vente", "location", "vente_et_location", "recherche", "autre") else "autre",
        "type_bien": obj.get("type_bien") if obj.get("type_bien") in
                     ("condo", "maison", "townhouse", "terrain", "commerce", "inconnu") else "inconnu",
        "prix_vente_thb": ent(obj.get("prix_vente_thb")),
        "loyer_mensuel_thb": ent(obj.get("loyer_mensuel_thb")),
        "surface_sqm": ent(obj.get("surface_sqm")),
        "chambres": ent(obj.get("chambres")),
        "salles_de_bain": ent(obj.get("salles_de_bain")),
        "nom_immeuble": str(obj.get("nom_immeuble") or "").strip(),
        "station_proche": str(obj.get("station_proche") or "").strip(),
        "quartier": str(obj.get("quartier") or "").strip(),
        "meuble": bool(obj.get("meuble")),
        "confiance": min(5, max(1, ent(obj.get("confiance")) or 1)),
    }
    d["vendeur"] = deduire_vendeur(post, obj.get("vendeur"))
    d["quota"] = deduire_quota(post)
    d.update({"auteur": post.get("author"), "date": post.get("date"), "lien": post.get("link"),
              "groupe": post.get("group"), "texte": post.get("content")})
    return d


def extraire(posts: list[dict], appel=appeler_claude, journal=print) -> tuple[list[dict], int, float]:
    """Rend (fiches extraites, nb d'échecs, coût USD)."""
    fiches, echecs, cout = [], 0, 0.0
    for debut in range(0, len(posts), LOT):
        lot = posts[debut:debut + LOT]
        try:
            texte, c = appel(prompt_lot(lot))
            cout += c
            objets = parser_reponse(texte, len(lot))
        except AuthClaudeExpiree:
            raise                    # inutile de tenter les lots suivants
        except Exception as e:                                      # noqa: BLE001
            journal(f"  lot {debut // LOT + 1} : échec appel — {e}")
            objets = [None] * len(lot)
        for post, obj in zip(lot, objets):
            if obj is None:
                echecs += 1
                continue
            fiches.append(normaliser(obj, post))
        journal(f"  lot {debut // LOT + 1}/{-(-len(posts) // LOT)} : "
                f"{sum(o is not None for o in objets)}/{len(lot)} extraites")
    return fiches, echecs, cout


# ─── Aval : rapprochement + chargement (outils existants, appelés tels quels) ─
def resoudre(extrait: Path, journal=print) -> Path:
    r = subprocess.run(["node", "immo-resolve.mjs", str(extrait)], cwd=SOCIAL,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    for ligne in (r.stdout or "").splitlines()[-6:]:
        journal(f"  resolve | {ligne}")
    if r.returncode != 0:
        raise RuntimeError(f"immo-resolve code {r.returncode} : {(r.stderr or '')[-300:]}")
    return extrait.with_name(extrait.name.replace(".json", "_resolu.json"))


def charger(resolu: Path, journal=print) -> int:
    r = subprocess.run([str(PY), str(LOADER), str(resolu), "--sqlite"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    for ligne in (r.stdout or "").splitlines()[-4:]:
        journal(f"  load | {ligne}")
    if r.returncode != 0:
        raise RuntimeError(f"load_social_leads code {r.returncode} : {(r.stderr or '')[-300:]}")
    m = re.search(r"→ (\d+) uniques", r.stdout or "")
    return int(m.group(1)) if m else 0


def _est_collecte(p: Path) -> bool:
    return not any(t in p.name for t in ("_extrait", "_resolu", "_charge"))


def a_traiter() -> list[Path]:
    """Les collectes sans `_charge.json` : l'état, c'est le disque."""
    fichiers = sorted(p for p in OUT.glob("immo_*.json") if _est_collecte(p))
    return [p for p in fichiers if not p.with_name(p.stem + "_charge.json").exists()]


def traiter_fichier(src: Path, journal=print, appel=appeler_claude) -> dict:
    posts = json.loads(src.read_text(encoding="utf-8")).get("posts") or []
    extrait = src.with_name(src.stem + "_extrait.json")
    if extrait.exists():
        fiches = json.loads(extrait.read_text(encoding="utf-8"))
        echecs, cout = 0, 0.0
        journal(f"  {src.name} : extraction déjà faite ({len(fiches)} fiches), reprise à l'aval")
    else:
        journal(f"  {src.name} : {len(posts)} posts à extraire ({MODELE}, lots de {LOT})")
        fiches, echecs, cout = extraire(posts, appel=appel, journal=journal)
        if not fiches and posts:
            raise RuntimeError("aucune fiche extraite : le modèle n'a rien rendu d'exploitable")
        extrait.write_text(json.dumps(fiches, ensure_ascii=False, indent=2), encoding="utf-8")
    resolu = resoudre(extrait, journal)
    fiches_res = json.loads(resolu.read_text(encoding="utf-8"))
    chargees = charger(resolu, journal)
    src.with_name(src.stem + "_charge.json").write_text(json.dumps(
        {"charge_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "chargees": chargees, "fiches": len(fiches)}), encoding="utf-8")
    return {"fichier": src.name, "posts": len(posts), "extraites": len(fiches),
            "echecs_extraction": echecs, "annonces": sum(1 for f in fiches if f.get("est_une_annonce")),
            "resolues": sum(1 for f in fiches_res if f.get("condo_lowi")),
            "chargees": chargees, "cout_usd": round(cout, 3)}


def run(led, run_id: int, lane: str, spec: dict) -> dict:
    journal = lambda m: print(m, flush=True)                          # noqa: E731
    OUT.mkdir(parents=True, exist_ok=True)

    # Garde-fou : la collecte tourne-t-elle encore ?
    # Trié par date de fichier, pas par nom : "immo_facebook_2026-07-25" passe
    # APRÈS "immo_2026-09-12" dans l'ordre alphabétique — le premier run
    # annonçait 1 197 h de silence sur une collecte de la veille.
    collectes = sorted((p for p in OUT.glob("immo_*.json") if _est_collecte(p)),
                       key=lambda p: p.stat().st_mtime)
    age_h = None
    if collectes:
        age_h = (datetime.now(timezone.utc) - datetime.fromtimestamp(collectes[-1].stat().st_mtime, timezone.utc)).total_seconds() / 3600
    if not collectes or age_h > COLLECTE_MUETTE_H:
        led.finding("social-leads", "medium", "collecte_facebook_muette",
                    f"aucune collecte Facebook depuis {age_h:.0f} h" if collectes else
                    "aucune collecte Facebook dans scraper/output/social/",
                    {"dernier": collectes[-1].name if collectes else None,
                     "tache": "LowiBKK-ScrapeImmoFacebook", "logs": "ops/logs/facebook/"}, run_id)

    fichiers = a_traiter()
    m = {"fichiers": 0, "posts": 0, "extraites": 0, "echecs_extraction": 0,
         "annonces": 0, "resolues": 0, "chargees": 0, "cout_usd": 0.0,
         "collecte_age_h": round(age_h, 1) if age_h is not None else None, "detail": []}
    if not fichiers:
        journal("  rien à traiter (toutes les collectes ont leur _extrait_resolu.json)")
        return m
    for src in fichiers:
        t0 = time.time()
        try:
            d = traiter_fichier(src, journal)
        except AuthClaudeExpiree as e:
            # UN constat pour la panne, pas un par fichier en attente : le
            # 2026-09-29 elle en produisait 6 de sévérité moyenne, sans cause.
            # Haute : rien ne se rétablit sans action humaine, et les
            # collectes s'empilent (le marqueur _charge.json manque → elles
            # seront toutes reprises dès la reconnexion, rien n'est perdu).
            led.finding("social-leads", "high", "claude_cli_non_authentifie",
                        f"claude -p non authentifié — {len(fichiers)} collecte(s) en attente, "
                        f"lancer `claude` puis /login sur ce poste : {e}",
                        {"en_attente": [p.name for p in fichiers]}, run_id)
            journal(f"  ✗ authentification claude -p : {e} — arrêt, {len(fichiers)} collecte(s) en attente")
            m["detail"].append({"erreur": f"auth : {str(e)[:200]}", "en_attente": len(fichiers)})
            break
        except Exception as e:                                          # noqa: BLE001
            led.finding("social-leads", "medium", "aval_social_echec",
                        f"{src.name} : {e}", {"fichier": src.name}, run_id)
            journal(f"  ✗ {src.name} : {e}")
            m["detail"].append({"fichier": src.name, "erreur": str(e)[:300]})
            continue
        d["secondes"] = round(time.time() - t0, 1)
        m["detail"].append(d)
        m["fichiers"] += 1
        for k in ("posts", "extraites", "echecs_extraction", "annonces", "resolues", "chargees", "cout_usd"):
            m[k] += d[k]
    m["cout_usd"] = round(m["cout_usd"], 3)
    if m["posts"] and m["echecs_extraction"] > 0.3 * m["posts"]:
        led.finding("social-leads", "medium", "extraction_degradee",
                    f"{m['echecs_extraction']}/{m['posts']} posts sans extraction exploitable",
                    {"modele": MODELE}, run_id)
    return m


if __name__ == "__main__":
    class _Led:                       # rejeu manuel : les findings s'impriment
        def finding(self, agent, sev, kind, msg, detail=None, run_id=None):
            print(f"  [finding {sev}] {kind} : {msg}")
    if len(sys.argv) > 1:
        print(json.dumps(traiter_fichier(Path(sys.argv[1])), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run(_Led(), 0, "manuel", {}), ensure_ascii=False, indent=1))

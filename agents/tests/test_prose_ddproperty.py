"""test_prose_ddproperty.py — l'IA locale sert-elle à quelque chose sur la PROSE ?

CE QUI EST TESTÉ, ET POURQUOI CE JEU-LÀ.
Le descriptif DDproperty (28 % des annonces) n'est pas un tableau de specs comme
chez FazWaz : c'est du marketing traduit automatiquement du thaï, et il décrit
LE PROJET, pas le lot. Mesuré sur 4 035 fiches : nombre de lots 74 %, bâtiments
32 %, promoteur 12 % — contre étage du lot 14 % et vue 0 %. Demander l'étage de
l'appartement à ce texte, c'est demander ce qui n'y est pas : le modèle trouve
« 41 floors » (la tour) et le rend. C'est vraisemblablement l'origine des 92 %
d'invention mesurés le 2026-08-02 quand on l'interrogeait là où la regex se tait.

On teste donc la question UTILE : ce texte peut-il alimenter le référentiel
`condos`, où `year_built` est à 0 % ?

TROIS ÉTIQUETTES, pas deux — c'est ce qui rend le test discriminant :
  · une valeur  → le texte l'énonce sans ambiguïté
  · null        → le fait est ABSENT
  · "ambigu"    → le fait est présent mais le texte se contredit. Deux tours de
                  hauteurs différentes (« 22 and 24 floors »), ou traduction
                  cassée (« The Breeze Narathiwas is a 374-storey high-rise »,
                  « 36 story 1 storey building »). Ici la bonne réponse est de
                  S'ABSTENIR : il n'existe pas de valeur juste.

MODE EXTRACTION. Le modèle ne rend pas un nombre : il ÉNUMÈRE les valeurs qu'il
voit et ce qu'elles désignent. C'est le code qui tranche — une seule valeur
distincte est retenue, plusieurs valent abstention. C'est cette architecture qui
avait fait passer l'abstention de 0 % à 77 % sur les doublons, à justesse égale.

Lancement :  scraper/.venv/Scripts/python.exe agents/tests/test_prose_ddproperty.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agents.core import local_llm  # noqa: E402

JEU = os.path.join(ROOT, "agents", "tests", "ddproperty_prose.json")
AMBIGU = "ambigu"

# ───────────────────────────── référence déterministe ─────────────────────────
# Même doctrine que pipeline/details.py : on énumère, et on n'ose une valeur que
# si elle est unique. Un texte qui donne deux hauteurs n'en donne aucune.

_ETAGES = re.compile(r"\b(\d{1,3})[- ]?(?:stor(?:e?y|ies)|floors?)\b", re.I)
_LOTS = re.compile(r"\b([\d,]{2,6})\s+(?:residential\s+)?units\b", re.I)
_PROMO = re.compile(
    r"(?:developed by|Developer\s*:|Project developer\s*:)\s*"
    r"([A-Z][\w.&()\- ]{3,55}?)"
    r"(?=\s*(?:Public Company|Company Limited|Co\.|Plc|Ltd|located|at |in |with|,|\.|$))",
    re.I)

# Hauteurs impossibles : la plus haute tour résidentielle de Bangkok fait ~78
# étages. « 374-storey » est une traduction cassée, pas un gratte-ciel.
ETAGE_MAX = 80
LOTS_MIN, LOTS_MAX = 10, 5000


def _unique(valeurs: list[int]):
    """Une seule valeur distincte → on la retient. Plusieurs → abstention."""
    v = sorted(set(valeurs))
    if not v:
        return None
    return v[0] if len(v) == 1 else AMBIGU


def regex_extrait(texte: str) -> dict:
    et = [int(m.group(1)) for m in _ETAGES.finditer(texte)]
    et = [x for x in et if 1 <= x <= ETAGE_MAX]
    lo = [int(m.group(1).replace(",", "")) for m in _LOTS.finditer(texte)]
    lo = [x for x in lo if LOTS_MIN <= x <= LOTS_MAX]
    m = _PROMO.search(texte)
    return {"nb_etages": _unique(et), "nb_lots": _unique(lo),
            "promoteur": m.group(1).strip(" .,") if m else None}


# ─────────────────────────────── mode extraction ──────────────────────────────
# Prompt COURT : mesuré 92 % pour des règles brèves contre 69 % pour une
# procédure verbeuse. On ne demande AUCUN jugement, seulement un relevé.
SYSTEM = """You read a real-estate blurb about a Bangkok condo BUILDING.
Report only what the text states. Never infer, never average, never pick a "main" value.

Return JSON:
{"floor_counts":[int],"unit_counts":[int],"developer":str|null}

floor_counts: every distinct storey/floor count given for a RESIDENTIAL tower.
  Skip car parks, basements, and floors named as a location (e.g. "on the 8th floor").
unit_counts: every distinct total-units figure for the project.
  Skip per-floor counts and commercial units.
developer: the company that developed the project, as written. null if absent.
List every value you see. Do not choose between them."""

SCHEMA = {"floor_counts": "any", "unit_counts": "any", "developer": "str?"}


def _ints(v) -> list[int]:
    out = []
    for x in v if isinstance(v, list) else []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            pass
    return out


def ia_extrait(texte: str) -> dict | None:
    """Le modèle CONSTATE, la fonction DÉCIDE. C'est toute la différence."""
    r = local_llm.ask_safe(SYSTEM, texte, SCHEMA, num_predict=300)
    if r is None:
        return None
    et = [x for x in _ints(r.get("floor_counts")) if 1 <= x <= ETAGE_MAX]
    lo = [x for x in _ints(r.get("unit_counts")) if LOTS_MIN <= x <= LOTS_MAX]
    p = r.get("developer")
    return {"nb_etages": _unique(et), "nb_lots": _unique(lo),
            "promoteur": (p or "").strip(" .,") or None}


# ──────────────────────────────── notation ────────────────────────────────────
def _promo_egal(a, b) -> bool:
    """Comparaison indulgente sur la raison sociale : « AP Thailand » et
    « AP (Thailand) Public Company Limited » désignent le même promoteur. On
    compare les mots significatifs, pas la chaîne."""
    if a is None or b is None:
        return a is None and b is None
    vide = {"public", "company", "limited", "co", "ltd", "plc", "the", "group",
            "development", "developments", "property", "properties", "real", "estate"}
    mots = lambda s: {w for w in re.findall(r"\w+", str(s).lower()) if w not in vide}
    ma, mb = mots(a), mots(b)
    return bool(ma) and bool(mb) and bool(ma & mb)


def note(preds: list[dict], verites: list[dict], champ: str) -> dict:
    """Trois populations disjointes, notées séparément — une moyenne globale
    masquerait qu'un extracteur peut être juste ET incapable de se taire."""
    ferme = juste = 0          # le texte donne une valeur : est-elle bonne ?
    amb = abstenu = 0          # texte contradictoire : s'est-il tu ?
    absent = silence = 0       # fait absent : n'a-t-il rien inventé ?
    for p, v in zip(preds, verites):
        attendu, obtenu = v[champ], (p or {}).get(champ)
        if attendu == AMBIGU:
            amb += 1
            abstenu += obtenu in (AMBIGU, None)
        elif attendu is None:
            absent += 1
            silence += obtenu is None
        else:
            ferme += 1
            juste += (_promo_egal(obtenu, attendu) if champ == "promoteur"
                      else obtenu == attendu)
    pc = lambda a, b: (100.0 * a / b) if b else float("nan")
    return {"n_ferme": ferme, "justesse": pc(juste, ferme),
            "n_ambigu": amb, "abstention": pc(abstenu, amb),
            "n_absent": absent, "silence": pc(silence, absent)}


def tableau(titre: str, preds, verites) -> None:
    print(f"\n  {titre}")
    print(f"    {'champ':11s}{'juste':>16s}{'abstention':>18s}{'silence':>16s}")
    for ch in ("nb_etages", "nb_lots", "promoteur"):
        s = note(preds, verites, ch)
        print(f"    {ch:11s}"
              f"{s['justesse']:>11.0f} % /{s['n_ferme']:<3d}"
              f"{s['abstention']:>13.0f} % /{s['n_ambigu']:<3d}"
              f"{s['silence']:>11.0f} % /{s['n_absent']:<3d}")


def main() -> int:
    jeu = json.load(open(JEU, encoding="utf-8"))
    verites = [l["verite"] for l in jeu]
    textes = [" ".join(l["extraits"]) for l in jeu]

    t0 = time.time()
    p_regex = [regex_extrait(t) for t in textes]
    t_regex = time.time() - t0

    ok, msg = local_llm.health()
    if not ok:
        print(f"Ollama indisponible ({msg}) — seule la référence regex est notée.")
        tableau(f"REGEX  ({t_regex:.2f} s au total)", p_regex, verites)
        return 1

    t0 = time.time()
    p_ia, pannes = [], 0
    for i, t in enumerate(textes, 1):
        r = ia_extrait(t)
        pannes += r is None
        p_ia.append(r)
        if i % 20 == 0:
            print(f"    … {i}/{len(textes)}  ({time.time()-t0:.0f} s)", flush=True)
    t_ia = time.time() - t0

    print("\n" + "=" * 62)
    tableau(f"REGEX  ({t_regex:.2f} s au total)", p_regex, verites)
    tableau(f"IA LOCALE  ({t_ia:.0f} s, {t_ia/len(textes):.1f} s/annonce, "
            f"{pannes} panne(s))", p_ia, verites)

    json.dump({"regex": p_regex, "ia": p_ia},
              open(os.path.join(ROOT, "agents", "tests", "prose_predictions.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # LÀ OÙ LA REGEX PARLE : l'IA fait-elle mieux qu'elle ?
    # C'est l'hypothèse « affineur » — le modèle ne découvre pas, il précise.
    print("\n  Là où la REGEX parle ET qu'une vérité existe")
    for ch in ("nb_etages", "nb_lots", "promoteur"):
        cas = [(a, b, v) for a, b, v in zip(p_regex, p_ia, verites)
               if a[ch] not in (None, AMBIGU) and v[ch] not in (None, AMBIGU)]
        eg = lambda x, y: _promo_egal(x, y) if ch == "promoteur" else x == y
        r_ok = sum(1 for a, _, v in cas if eg(a[ch], v[ch]))
        i_ok = sum(1 for _, b, v in cas if b and eg(b[ch], v[ch]))
        print(f"    {ch:11s} n={len(cas):<3d} regex {100*r_ok/max(1,len(cas)):>3.0f} % | "
              f"IA {100*i_ok/max(1,len(cas)):>3.0f} %")

    # Le seul chiffre qui décide : l'IA ajoute-t-elle des faits JUSTES là où la
    # regex se tait ? C'est exactement la question qui avait rendu 92 %
    # d'invention le 2026-08-02.
    print("\n  Là où la REGEX se tait — que dit l'IA ?")
    for ch in ("nb_etages", "nb_lots", "promoteur"):
        muet = [(a, b, v) for a, b, v in zip(p_regex, p_ia, verites)
                if a[ch] is None]
        parle = [(a, b, v) for a, b, v in muet if b and b[ch] not in (None, AMBIGU)]
        bon = sum(1 for _, b, v in parle
                  if (_promo_egal(b[ch], v[ch]) if ch == "promoteur" else b[ch] == v[ch]))
        print(f"    {ch:11s} regex muette sur {len(muet):>3d} | IA ose {len(parle):>3d} | "
              f"juste {bon:>3d}" +
              (f"  → {100*bon/len(parle):.0f} % de justesse, "
               f"{100-100*bon/len(parle):.0f} % d'invention" if parle else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

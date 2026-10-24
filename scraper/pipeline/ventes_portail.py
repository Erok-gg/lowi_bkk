"""Ventes « conclues » publiées par un portail sur sa page d'immeuble.

SOURCE FAIBLE, et tenue à l'écart des annonces : tables `ventes_portail` et
`ventes_portail_projets`, jamais mêlées à `listings` ni aux statistiques de
marché (décision du 2026-10-22). Raison mesurée le même jour sur 10 immeubles :
FazWaz en publie 4 à 17 par immeuble sur ~8 ans (≈ 2 par an), 4 immeubles sur 10
n'en ont aucune, et l'origine n'est pas indiquée (7 ventes sur 53 seulement se
rapprochent d'une de nos annonces disparues ; notre historique ne commence qu'en
06/2026). Ni registre foncier prouvé, ni échantillon représentatif : un chiffre
à afficher étiqueté, pas à moyenner avec nos médianes.

FazWaz : le composant `<previous-sales :data='[...]'>` de la page d'immeuble
embarque le JSON des ventes, et une phrase de synthèse écrite par FazWaz (nombre
de ventes, prix/m², jours avant vente, décote sur le prix affiché). Page déjà
lue pour le nombre de logements (`adapters/fazwaz.lire_projet`) : AUCUNE requête
de plus. Les chemins `/api/` et `/graphql` ne sont pas appelés (interdits par
robots.txt).
"""
from __future__ import annotations

import html as _html
import json
import re

# L'attribut se termine par « ' » suivi de l'attribut Vue suivant (` :active-tab-index`),
# pas par « '> » : le `v-if` qui précède contient lui-même des apostrophes.
_COMPOSANT = re.compile(r"<previous-sales\b[^>]*?:data='(.*?)'\s+:", re.S)
_RESUME = (
    ("n", re.compile(r"last ([\d,]+) sales transactions")),
    ("price_per_sqm", re.compile(r"price per sqm of these sales was\s*\D{0,3}([\d,]+)")),
    ("jours_avant_vente", re.compile(r"listed for an average of ([\d,]+) days")),
    ("decote_pct", re.compile(r"sales prices were ([\d.]+)% (below|above) the initial listing")),
)


def _f(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def _resume(texte: str) -> dict:
    """Phrase de synthèse que FazWaz écrit lui-même (« …29 sales transactions…
    159,000/m²… 715 days… 7% below the initial listing prices »). Ce sont SES
    chiffres, calculés sur SA base : à citer comme tels, pas à recalculer.
    `decote_pct` > 0 = vendu EN DESSOUS du prix affiché."""
    r = {}
    for cle, motif in _RESUME:
        m = motif.search(texte or "")
        if not m:
            continue
        v = float(m.group(1).replace(",", ""))
        r[cle] = -v if cle == "decote_pct" and m.group(2) == "above" else v
    return r


def lire_fazwaz(page: str) -> tuple[list[dict], dict]:
    """(ventes, résumé) de la page d'immeuble FazWaz. Champ absent → None, jamais
    deviné. Page sans composant ou JSON illisible → ([], {}) : ne fait jamais
    échouer le scrap."""
    m = _COMPOSANT.search(page or "")
    if not m:
        return [], {}
    try:
        blocs = json.loads(_html.unescape(m.group(1)))
    except ValueError:
        return [], {}
    out, resume = [], {}
    for bloc in blocs if isinstance(blocs, list) else []:
        if not isinstance(bloc, dict):
            continue
        deal = "rent" if str(bloc.get("saleType", "")).lower() == "forrent" else "sale"
        if deal == "sale" and not resume:
            resume = _resume(bloc.get("description"))
        for u in bloc.get("units") or []:
            prix, date_ = _f(u.get("sold_price")), (u.get("sold_date") or "")[:10]
            if not prix or not re.match(r"\d{4}-\d{2}-\d{2}$", date_):
                continue
            surface = _f(u.get("unit_area")) or _f(u.get("indoor_area"))
            titre = (u.get("property_ownership_title") or "").lower()
            out.append({
                "unit_id": u.get("unit_id"), "deal_type": deal, "sold_date": date_,
                "sold_price": prix, "area_sqm": surface,
                "price_per_sqm": prix / surface if surface and surface > 5 else None,
                "floor": u.get("floor_number"), "bedrooms": u.get("bedrooms"),
                "furniture": u.get("furniture_option"),
                "quota": "thai" if "thai" in titre else "foreigner" if "foreign" in titre else None})
    return out, resume

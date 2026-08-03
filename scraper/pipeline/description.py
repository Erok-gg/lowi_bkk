"""description.py — capture du descriptif libre d'une annonce.

Jusqu'au 2026-07-31, AUCUN texte libre n'était stocké : `raw_data` ne contenait
que des scalaires (prix, chambres, nom d'immeuble, district). Vérifié en base :
`count(*) filter (where raw_data ? 'description') = 0` sur les 4 sources.

Conséquence : le « motif du vendeur » qui apparaît dans les études de cas venait
entièrement de l'audit humain, jamais de la donnée. C'est aussi ce qui privait
l'étage d'analyse locale de matière — un modèle qui n'a que des nombres à lire
ne fait que refaire du SQL, en moins fiable.

Ce module est volontairement défensif : un descriptif absent n'est jamais une
panne, et ne doit jamais faire échouer un scrap.
"""
from __future__ import annotations

import html as _html
import json
import re

# Bornes : au-delà, on tronque. Un descriptif d'annonce dépasse rarement 4 000
# caractères ; au-delà on ramasse du gabarit de page, pas du texte d'annonce.
MIN_LEN = 40
MAX_LEN = 4000

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t ]+")
_NL = re.compile(r"\n{3,}")

# Retirer les balises ne suffit pas : le CONTENU de <script>/<style> resterait et
# se retrouverait dans le descriptif sous forme de CSS. Ces blocs se suppriment
# en entier, avant tout autre traitement.
_NOISE = re.compile(r"<(script|style|noscript|template)\b[^>]*>.*?</\1>", re.I | re.S)
# Signature de code résiduel : si on trouve ça dans un « descriptif », c'est du
# gabarit de page, pas du texte d'annonce.
_LOOKS_LIKE_CODE = re.compile(
    r"(\{\s*[\w-]+\s*:\s*[^;{}]+;)"      # regle CSS
    r"|(\bfunction\s*\()|(@media\b)|(\bvar\s+\w+\s*=)"
    r"|(\blet\s+\w+\s*=)|(=>\s*\{)"      # JS moderne / Alpine.js
    r"|(\$root\b)|(\bAlpine\b)|(\bwindow\.\w)|(\bdocument\.\w)"
    r"|(\.querySelector\()|(\baddEventListener\()")


def strip_noise(html: str | None) -> str:
    return _NOISE.sub(" ", html or "")


def looks_like_code(text: str | None) -> bool:
    return bool(_LOOKS_LIKE_CODE.search(text or ""))


_META = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\'](.*?)["\']',
    re.I | re.S)
_META_REV = re.compile(
    r'<meta[^>]+content=["\'](.*?)["\'][^>]+(?:name|property)=["\'](?:og:)?description["\']',
    re.I | re.S)
_LDJSON = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)


def clean(text: str | None) -> str | None:
    """Détague, déséchappe, normalise les blancs. Rend None si trop court."""
    if not text:
        return None
    t = _TAGS.sub(" ", text)
    t = _html.unescape(t)
    t = t.replace("\r", "\n")
    t = _WS.sub(" ", t)
    t = _NL.sub("\n\n", t)
    t = "\n".join(line.strip() for line in t.split("\n")).strip()
    # Du code peut subsister APRES le texte utile : les pages FazWaz portent des
    # attributs Alpine.js multi-lignes, et le detagueur `<[^>]+>` se casse sur les
    # fonctions flechees — le `>` de `(url) => {` termine la balise trop tot, si
    # bien que la fin de l'attribut retombe dans le texte. Plutot que de jeter une
    # description dont la prose est bonne, on la COUPE au debut du code.
    m = _LOOKS_LIKE_CODE.search(t)
    if m:
        # On coupe au motif, puis on retire la ponctuation orpheline laissee
        # devant lui (accolade/parenthese ouvrante, separateurs).
        t = re.sub(r"[\s{(\[<:;,|/\\-]+$", "", t[:m.start()])
    if len(t) < MIN_LEN:
        return None
    return t[:MAX_LEN]


# Un nœud décrivant le SITE ou l'AGENCE porte lui aussi une clé `description` —
# et c'est du texte de marque, identique sur les 20 000 annonces. Relevé sur
# FazWaz : le ld+json de la fiche contient « The most popular property website
# about condo… », qui n'a rien à voir avec le bien. Le capturer serait pire que
# de ne rien capturer : ça remplirait la colonne de bruit indiscernable.
TYPES_HORS_ANNONCE = {
    "organization", "website", "webpage", "realestateagent", "localbusiness",
    "breadcrumblist", "sitenavigationelement", "searchaction", "person",
}


def from_blob(node, key: str = "description"):
    """Cherche récursivement une `description` exploitable dans un blob
    (__NEXT_DATA__, ld+json…), en ignorant les sous-arbres qui décrivent le site
    ou l'agence. Rend le PLUS LONG candidat : les blobs portent souvent une
    description courte de vignette à côté du texte complet."""
    best: str | None = None
    stack = [node]
    seen = 0
    while stack and seen < 20000:
        cur = stack.pop()
        seen += 1
        if isinstance(cur, dict):
            t = cur.get("@type") or cur.get("type")
            if isinstance(t, str) and t.lower() in TYPES_HORS_ANNONCE:
                continue          # sous-arbre de marque : on n'y descend pas
            for k, v in cur.items():
                if isinstance(v, str) and k.lower() in (key, "descriptiontext", "fulldescription"):
                    c = clean(v)
                    if c and (best is None or len(c) > len(best)):
                        best = c
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(x for x in cur if isinstance(x, (dict, list)))
    return best


# Certaines fiches ne portent le texte que dans le HTML, sous un intertitre.
# FazWaz : « About This Condo », suivi du descriptif complet — alors que sa
# meta description est tronquée à ~160 caractères par un « … ».
_HEADINGS = re.compile(
    r"(?:About\s+This\s+\w+|Property\s+Description|Description)\s*",
    re.I)


def from_heading(html: str, max_chars: int = 3000) -> str | None:
    """Texte qui suit un intertitre de description dans le HTML."""
    if not html:
        return None
    texte = _TAGS.sub(" ", strip_noise(html))
    texte = _html.unescape(texte).replace("\xa0", " ")
    texte = _WS.sub(" ", texte)
    m = _HEADINGS.search(texte)
    if not m:
        return None
    return clean(texte[m.end():m.end() + max_chars])


def from_ldjson(html: str) -> str | None:
    """Descriptif porté par un bloc ld+json (Nestopa, FazWaz)."""
    best: str | None = None
    for raw in _LDJSON.findall(html or ""):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        c = from_blob(data)
        if c and (best is None or len(c) > len(best)):
            best = c
    return best


def from_meta(html: str) -> str | None:  # noqa: D401
    """Dernier recours : la balise meta description. Souvent tronquée à ~160
    caractères, donc de moindre valeur — mais mieux que rien."""
    for rx in (_META, _META_REV):
        m = rx.search(html or "")
        if m:
            c = clean(m.group(1))
            if c:
                return c
    return None


def texte_integral(html: str | None) -> str | None:
    """TEXTE COMPLET de la page, nettoye mais NON tronque.

    POURQUOI ON LE CONSERVE (2026-08-02). `description` est un produit fini :
    tronque a 4000 caracteres (8 % des fiches le sont), coupe au premier motif
    ressemblant a du code, et cadre sur le bloc utile. C'est ce qu'on veut
    afficher, pas ce qu'on veut ARCHIVER.

    Trois defauts d'extraction ont ete trouves dans la seule journee du
    2026-08-02 (etage confondu avec un titre, quota confondu avec une phrase
    legale, disclaimer de prix pris pour une affirmation). Chaque correction a
    pu etre rejouee parce que le texte etait encore la. Sans lui, il aurait
    fallu re-scraper — 22 heures.

    Cout mesure : ~8 ko par page, ~34 Mo compresses pour 15 000 annonces, contre
    3,2 Go d'images. Le rapport protection/cout n'est pas discutable.
    """
    if not html:
        return None
    t = _TAGS.sub(" ", strip_noise(html))
    t = _html.unescape(t).replace("\xa0", " ")
    t = _WS.sub(" ", t)
    t = _NL.sub("\n\n", t)
    t = "\n".join(l.strip() for l in t.split("\n")).strip()
    return t or None


def extract(html: str | None = None, blob=None) -> str | None:
    """Cascade, du plus fiable au moins fiable :
        blob structuré → intertitre HTML → ld+json → meta description.

    L'intertitre passe AVANT ld+json et meta parce qu'il porte le texte complet
    là où les deux autres sont soit du texte de marque, soit tronqués à ~160
    caractères. Ne lève jamais : un descriptif manquant n'est pas une panne."""
    try:
        candidats = []
        if blob is not None:
            candidats.append(from_blob(blob))
        if html:
            candidats += [from_heading(html), from_ldjson(html), from_meta(html)]
        for c in candidats:
            if c:
                return c
    except Exception:  # noqa: BLE001 — jamais bloquant
        return None
    return None

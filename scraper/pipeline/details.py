"""Extraction DETERMINISTE des attributs contenus dans les descriptifs.

Constat de l'analyse des 500 : chez FazWaz (63 %) et PropertyScout (9 %), le
descriptif est un TABLEAU DE SPECS rendu en texte, pas de la prose. Les valeurs
s'y lisent par motif, sans aucune interpretation. DDproperty (28 %) est de la
prose marketing sur le PROJET, pas sur le lot.

Meme enseignement que sur les doublons : la part majoritaire du travail est
deterministe. Le modele local n'a de sens que sur le residu.
"""
from __future__ import annotations

import re

# Chez FazWaz, un libelle est souvent suivi d'un PARAGRAPHE EXPLICATIF avant sa
# valeur ("CAM Fee The common area maintenance (CAM) fee has to be paid... ฿2,160/mo").
# On saute donc ce texte, mais sans jamais franchir un AUTRE libelle connu : c'est
# ce qui distingue "valeur eloignee" de "valeur absente".
_LIBELLES = (r"Floor|Bedrooms?|Size|Price per SqM|Pets|Condo Ownership|Property Ownership|"
             r"Furniture|View\(s\)|Unit Type|Building|CAM Fees?|Listed By|"
             r"Electricity [Pp]rice|Water [Pp]rice|Unit ID|Min\. Rental Duration|"
             r"Available From|Date Listed|Updated|Property Type|Project Name|Developer|"
             r"Construction|Floors|Buildings|Units|Project Area|Nearest Landmark|Location")

# La source ecrit "N/A" plutot que d'omettre le champ : ce n'est pas une valeur.
_VIDES = {"n/a", "na", "-", "none", "unknown", "", "n.a.", "tba", "n/a."}


def _vide(v) -> bool:
    return v is None or str(v).strip().lower() in _VIDES


def _apres(texte: str, libelle: str, motif: str):
    """Cherche `motif` juste apres `libelle`, sans franchir un autre libelle.

    Le libelle est enferme dans un groupe NON capturant, sinon une alternance
    casse la numerotation des groupes et group(1) ne designe plus l'intervalle.
    """
    m = re.search(rf"\b(?:{libelle})\b(.{{0,400}}?)(?:{motif})", texte, re.S)
    if not m:
        return None
    if re.search(rf"\b(?:{_LIBELLES})\b", m.group(1) or ""):
        return None
    return m


def etage(t: str):
    """Etage du lot.

    Le TIRET est le discriminant : "Floor 2-Bedroom Condo at ..." est un TITRE
    d'annonce (le 2 vient de "2-Bedroom"), alors que "Floor 7 Bedroom Studio"
    est la valeur 7 suivie du champ suivant. Faux positif releve sur donnees reelles.
    """
    # Le nombre doit SUIVRE IMMEDIATEMENT le libelle. Avec une fenetre large,
    # deux faux positifs mesures le 2026-08-02 :
    #   "Floor, 117 Units Construction Status"  -> 117 etait le nombre de LOTS
    #   "high Floor with Breathtaking Views..."  -> "Floor" en prose marketing,
    #                                               le nombre venait bien plus loin
    # 50 annonces annoncaient plus de 60 etages, dont 117 — au-dessus de la plus
    # haute tour de Bangkok. On exige donc l'adjacence, et on refuse un nombre
    # suivi d'une unite qui trahit un autre champ.
    # FORME 1 — le nombre PRECEDE le libelle : "26th Floor 72 sq.m.", "25 Floor".
    # Prioritaire, car dans ces phrases le nombre qui SUIT est la surface :
    # sur "26th Floor 72 sq.m." on retenait 72 au lieu de 26.
    m = re.search(r"\b(\d{1,3})(?:st|nd|rd|th)?\s+Floor\b", t)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 80:
            return n
    # FORME 2 — le nombre SUIT le libelle : "Floor 41 Bedroom 1".
    # Les exclusions couvrent les unites qui trahissent un AUTRE champ :
    # "Floor, 117 Units" (nombre de lots), "Floor 72 sq.m." (surface).
    m = re.search(r"\bFloor\b[ :]{0,3}(\d{1,3})\b"
                  r"(?!\s*(?:-\s*(?:[Bb]ed|[Bb]ath)|[Uu]nits?|sq\s?\.?\s?m|square\s+met|m²|SqM))",
                  t, re.I)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 80:      # plus haute tour residentielle de Bangkok : ~78
            return n
    m = re.search(r"located on the (\d{1,3})(?:st|nd|rd|th) floor", t, re.I)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 80 else None
    return None


# Charges de copropriete plausibles, en THB par m2 et par mois. Meme doctrine que
# lib/market-bounds.ts : une valeur hors bornes n'est pas une aubaine ni un piege
# a signaler, c'est une donnee a ECARTER des statistiques. Releve sur 3 389
# valeurs reelles : moyenne 54, et 95 % entre 20 et 120.
CAM_MIN_M2, CAM_MAX_M2 = 15.0, 150.0


def cam_fee_brut(t: str):
    """(montant, unite) tels qu'ecrits. L'unite compte : la source peut donner un
    total mensuel (`฿1,887/mo`) ou un tarif au m2 (`฿55/sqm`) — les confondre
    fausse la valeur d'un facteur egal a la surface."""
    m = _apres(t, r"CAM Fees?", r"฿\s*([\d,]+)\s*/\s*(mo|month|sqm)")
    if not m:
        return None
    return float(m.group(2).replace(",", "")), m.group(3).lower()


def cam_fee(t: str, area_sqm: float | None = None):
    """Charges de copropriete MENSUELLES en THB, ou None si invraisemblable.

    `area_sqm` sert a deux choses :
      · convertir un tarif au m2 en total mensuel ;
      · verifier la vraisemblance. Sans surface on ne peut que borner grossierement.

    Releve le 2026-08-02 : 157 valeurs sur 3 389 (4,6 %) sortent des bornes,
    dont Saranjai Mansion a 142 000 THB/mois pour 71 m2 (2 000 THB/m2) et des
    fiches a 1 THB — manifestement des valeurs de remplissage.
    """
    brut = cam_fee_brut(t)
    if not brut:
        return None
    v, unite = brut
    if unite == "sqm":
        if not area_sqm:
            return None          # tarif au m2 sans surface : inexploitable
        v *= area_sqm
    if not 0 < v < 500000:
        return None
    if area_sqm and area_sqm > 0:
        ratio = v / area_sqm
        if not CAM_MIN_M2 <= ratio <= CAM_MAX_M2:
            return None
    return v


def meuble(t: str):
    m = _apres(t, r"Furniture",
               r"(Fully Furnished|Partly Furnished|Partially Furnished|Unfurnished)")
    if m:
        return m.group(2).lower().replace("partially", "partly")
    if re.search(r"\bfully[- ]furnished\b", t, re.I):
        return "fully furnished"
    if re.search(r"\bunfurnished\b", t, re.I):
        return "unfurnished"
    return None


# "Blocked View" est une ANTI-VUE : la ranger avec les autres ferait monter un
# compteur "nombre de vues" alors qu'elle le dement. Elle est donc exclue du
# decompte, mais conservee dans le libelle — c'est une information de valeur.
_ANTI_VUE = re.compile(r"\bblocked\b", re.I)


def vues(t: str):
    """Liste COMPLETE des vues : "Skyline View, City View" rend les DEUX."""
    m = re.search(r"View\(s\)(.{0,180})", t, re.S)
    if not m:
        return None
    brut = re.split(r"\b(?:Unit Type|Building|CAM Fee|Electricity|Water|"
                    r"Listed By|Unit ID|Furniture|Pets|Project)\b", m.group(1))[0]
    if _vide(brut):
        return None
    out = [v.strip(" .,") for v in brut.split(",")]
    out = [v for v in out if 2 < len(v) < 40 and not _vide(v)]
    return out or None


def vues_n(t: str):
    """COMBIEN de vues degagees. Sert au tri et aux comparaisons.

    On ne cherche pas a decider si "Sky" et "Horizon View" sont deux vues ou
    deux mots pour la meme : la source les enonce separement, on les compte
    separement. Le LIBELLE reste a cote pour la nuance — c'est un commentaire
    lisible par un humain, pas une taxonomie a normaliser.
    """
    v = vues(t)
    if v is None:
        return None
    return sum(1 for x in v if not _ANTI_VUE.search(x))


def batiment(t: str):
    """Tour au sein de la residence : "Building A", "Building 2".

    Discriminant de doublon a part entiere : meme residence + tours differentes
    = lots forcement distincts. On n'accepte QU'UNE lettre ou UN nombre isole ;
    sur 207 formes relevees, les autres ne font que repeter le nom de la
    residence ("Building Life One Wireless") et n'apprennent rien.
    """
    m = re.search(r"\bBuilding\s+([A-Z]|\d{1,2})\s*(?=CAM Fees?|Listed By|Electricity|Water)", t)
    return m.group(1) if m else None


# Bornes de plausibilite des tarifs, memes principes que lib/market-bounds.ts.
# Tarif public thailandais : ~4-5 THB/kWh et ~9-19 THB/m3. Un bailleur revend
# couramment 7-8 et 20-25. Au-dela on est sur une faute de saisie : le releve du
# 2026-08-02 sort un 700 THB/kWh et un 420 THB/m3.
ELEC_MIN, ELEC_MAX = 3.0, 15.0
EAU_MIN, EAU_MAX = 8.0, 50.0

_TARIF_PUBLIC = re.compile(r"Government Rate", re.I)


def _tarif(t: str, libelle: str, unite: str, mini: float, maxi: float):
    m = re.search(rf"{libelle}\s*(Government Rate|฿\s*([\d.,]+)\s*/\s*{unite}|N/A)", t, re.I)
    if not m or not m.group(2):
        return None
    v = float(m.group(2).replace(",", ""))
    return v if mini <= v <= maxi else None


def elec_kwh(t: str):
    """Prix de l'electricite refacture, en THB/kWh. None si tarif public ou absent."""
    return _tarif(t, r"Electricity [Pp]rice", r"kWh", ELEC_MIN, ELEC_MAX)


def eau_m3(t: str):
    """Prix de l'eau refacturee, en THB/m3."""
    return _tarif(t, r"Water [Pp]rice", r"(?:Cubic Met\w*|Unit)", EAU_MIN, EAU_MAX)


def tarif_regime(t: str):
    """`government` = tarif public refacture sans marge ; `private` = tarif du bailleur.

    UNE seule colonne pour l'eau ET l'electricite : sur 1 451 annonces qui
    renseignent les deux, elles indiquent le MEME regime dans 1 445 cas. Deux
    colonnes auraient coute le double pour distinguer six annonces.

    L'enjeu est concret pour un locataire : 7 THB/kWh contre ~4,5 au tarif
    public, c'est ~55 % de surcout sur l'electricite.
    """
    # Un tarif CHIFFRE l'emporte sur la mention "Government Rate" : 6 annonces
    # affichent l'electricite a ฿6,00/kWh et l'eau au tarif public. Les classer
    # "government" masquerait la marge sur le poste le plus lourd — on retient
    # donc le cas defavorable au locataire, jamais l'inverse.
    if elec_kwh(t) is not None or eau_m3(t) is not None:
        return "private"
    zone = re.search(r"(Electricity [Pp]rice.{0,120}?Water [Pp]rice.{0,60})", t, re.S)
    if _TARIF_PUBLIC.search(zone.group(1) if zone else t):
        return "government"
    return None


_SUITE = r"(?=Furniture|Unit Type|Views?\b|View\(s\)|Building|CAM Fees?|Listed By|Electricity)"

# Le lot est EXPLICITEMENT en quota etranger.
_QUOTA_ETRANGER = re.compile(
    r"\bthis (?:unit|property|condo) is (?:under|in) (?:the )?foreign(?:er)? quota\b"
    r"|\bforeign(?:er)? quota (?:unit|available)\b"
    r"|\bavailable (?:in|under) foreign(?:er)? quota\b", re.I)

# DISCLAIMER DE PRIX, present sur 35 fiches PropertyScout : "Price shown applies
# to Thai quota units; foreign quota unit price may vary". Il parle de la
# TARIFICATION, pas du regime de CE lot — et il contient "foreign quota unit",
# donc le motif affirmatif ci-dessus l'attrape si on ne l'ecarte pas d'abord.
# Meme nature de piege que la phrase legale FazWaz.
_DISCLAIMER_PRIX = re.compile(r"price shown applies to thai quota", re.I)


def proprietaire(t: str):
    """NATIONALITE / structure du VENDEUR — thai | foreigner | company.

    A NE PAS CONFONDRE AVEC LE QUOTA (correction metier du 2026-08-02) : un
    proprietaire thai peut parfaitement detenir un lot en quota etranger. Le
    libelle PropertyScout "Property Ownership" decrit le vendeur, pas le regime
    de propriete du lot. Les fusionner produisait de faux quotas.
    """
    m = re.search(r"Property Ownership\s+([A-Za-z ]{2,20}?)\s*" + _SUITE, t)
    if not m:
        return None
    v = m.group(1).strip().lower()
    if _vide(v):
        return None
    if "thai" in v:
        return "thai"
    if "foreign" in v:
        return "foreigner"
    if "compan" in v:
        return "company"
    return None


def quota(t: str):
    """REGIME DE PROPRIETE du lot : thai | foreigner. Uniquement quand il est dit.

    Deux vocabulaires selon la source :

    FazWaz — libelle explicite "Thai Quota" / "Foreign Quota".
      PIEGE : une recherche insensible a la casse matche aussi la phrase LEGALE
      presente sur toutes les fiches ("Units that are part of the Thai quota or
      are being leased for 30 years..."). Sur 315 fiches : 123 vrais libelles
      contre 155 phrases legales, soit ~32 faux positifs. Le vrai libelle est un
      TITRE : casse exacte, suivi du champ suivant.

    PropertyScout — n'expose PAS le quota en champ structure. On le deduit :
      · vendeur etranger        -> quota etranger (en pleine propriete, un
                                   etranger ne peut detenir que du quota etranger)
      · mention explicite       -> "This unit is under foreign quota",
                                   "Foreign quota available"
      · vendeur thai seul       -> AUCUNE information : un thai detient l'un ou
                                   l'autre. On rend None plutot que de deviner.
    """
    m = re.search(r"\b(Thai|Foreign(?:er)?) Quota\b\s*" + _SUITE, t)
    if m:
        return "thai" if m.group(1) == "Thai" else "foreigner"

    if _QUOTA_ETRANGER.search(t) and not _DISCLAIMER_PRIX.search(t):
        return "foreigner"
    if proprietaire(t) == "foreigner":
        return "foreigner"
    return None


def animaux(t: str):
    """Angle mort revele par le modele local : la source ecrit aussi
    "Pets All Kind of Pets Allowed" ou "Pets Small Pets Allowed".

    On n'utilise PAS `_apres` ici : le mot "Pets" se repete dans la valeur
    elle-meme, et le garde-fou anti-libelle de `_apres` le prenait pour le champ
    suivant. Regex directe, fenetre courte."""
    m = re.search(r"\bPets\b[ A-Za-z]{0,26}?\b(Not Allowed|Allowed)\b", t)
    if not m:
        return None
    return m.group(1) == "Allowed"


def publie_par(t: str):
    """Proprietaire direct ou agence — utile pour la question des doublons."""
    m = _apres(t, r"Listed By", r"(Private Owner|Agent|Agency|Developer)")
    return m.group(2).lower() if m else None


def annee_construction(t: str):
    """ANNEE DE LIVRAISON — passee (immeuble debout) ou future (VEFA).

    Ne dit PAS si le bien existe : voir `livre()`. Les deux vont ensemble, et
    c'est le point souleve le 2026-08-02 — 151 annonces portaient une annee
    future (66 en 2026, 52 en 2027, 21 en 2028, 12 en 2029) rangee dans la meme
    colonne que des immeubles livres. Un bien 2029 ne se compare pas a un bien
    2013 : ni vetuste, ni rendement, ni disponibilite locative.
    """
    for motif in (r"Construction(?: Status)?:?\s*(?:Completed|Off Plan)\s*\(?\w{0,9}\s*(\d{4})\)?",
                  r"(?:was )?completed in (?:\w{3,9} )?(\d{4})",
                  r"Building completed in (\d{4})"):
        m = re.search(motif, t, re.I)
        if m:
            a = int(m.group(1))
            if 1960 <= a <= 2040:
                return a
    return None


def livre(t: str):
    """L'immeuble est-il LIVRE ? true | false | None.

    On lit le STATUT annonce par la source plutot que de comparer l'annee a la
    date du jour : la source sait, nous devinons. Vocabulaire releve sur 14 204
    fiches — "Completed" 6 529, "Off Plan" 47, "Wait for EIA" 1 (le projet
    n'a meme pas son autorisation environnementale).

    Repli sur l'annee quand le statut est absent : une livraison posterieure a
    l'annee en cours n'est pas encore intervenue.
    """
    from datetime import datetime
    an_courante = datetime.now().year

    # 1. CHAMP STRUCTURE de la source. Le plus fiable : c'est une valeur saisie,
    #    pas une phrase. 6 529 "Completed" et 47 "Off Plan" releves.
    if re.search(r"Construction(?: Status)?:?\s*Off[ -]?Plan\b", t, re.I):
        return False
    if re.search(r"Construction(?: Status)?:?\s*Completed\b", t, re.I):
        return True

    # 2. ANNEE de livraison. Elle prime sur la prose, et la mesure du 2026-08-02
    #    dit pourquoi : deux gabarits de PROSE se contredisent avec l'annee.
    #    · PropertyScout ecrit "Building completed in 2027" au passe pour une
    #      livraison A VENIR — 84 annonces declarees livrees pour 2027-2029.
    #    · L'inverse existe aussi : "the project is under construction and is
    #      expected to be completed in 2019" est un texte PERIME, jamais reecrit
    #      depuis 2017. L'immeuble est debout depuis des annees (233 cas).
    #    L'annee tranche les deux d'un coup.
    a = annee_construction(t)
    if a is not None:
        return a <= an_courante

    # 3. PROSE, en dernier recours seulement. "under construction" doit designer
    #    l'IMMEUBLE : il qualifie tres souvent une ligne de METRO voisine
    #    ("Opposite MRT Orange Line (under construction)"), ce qui est un
    #    argument de vente, pas un statut de chantier.
    if re.search(r"Wait for EIA|Pre[- ]sale", t, re.I):
        return False
    if re.search(r"(?<!\bLine )(?<!\bMRT )(?<!\bBTS )under construction", t, re.I) \
            and not re.search(r"(?:MRT|BTS|Line|Station|Expressway|Highway)[^.]{0,40}"
                              r"under construction", t, re.I):
        return False
    if re.search(r"(?:was |Building )?completed in (?:\w{3,9} )?\d{4}", t, re.I):
        return True
    return None


def promoteur(t: str):
    m = re.search(r"Developer:\s*([A-Z][^:]{2,45}?)"
                  r"(?=\s+(?:Construction|Floors|Buildings|Units|Project|Location|Nearest)\b)", t)
    if not m:
        return None
    v = m.group(1).strip(" .,")
    return None if _vide(v) else v


def duree_min_location(t: str):
    """Duree minimale de bail, en mois.

    La domination du 12 mois (4 044 cas contre 100 a 3 mois et 37 a 1 mois) m'a
    d'abord semble etre une valeur par defaut. C'est en realite le marche :
    la location courte duree est INTERDITE en copropriete en Thailande, donc le
    bail annuel est la norme. Le champ est donc exploitable tel quel.
    """
    m = _apres(t, r"Min\. Rental Duration", r"(\d+)\s*(Year|Month)")
    if not m:
        return None
    n = int(m.group(2))
    return n * 12 if m.group(3).lower().startswith("year") else n


def landmark(t: str):
    m = re.search(r"Nearest Landmark:?\s*([A-Za-z0-9 .'\-]+?)\s*-\s*([\d.]+)\s*Km", t)
    if not m or _vide(m.group(1)):
        return None
    return [m.group(1).strip(), float(m.group(2))]


def unite_ref(t: str):
    m = _apres(t, r"Unit ID", r"([A-Z]?\d{4,12})")
    return m.group(2) if m else None


CHAMPS = {
    "etage": etage,
    "cam_fee_thb": cam_fee,
    "meuble": meuble,
    "vues": vues,
    "vues_n": vues_n,
    "batiment": batiment,
    "elec_kwh": elec_kwh,
    "eau_m3": eau_m3,
    "tarif_regime": tarif_regime,
    "quota": quota,
    "proprietaire": proprietaire,
    "animaux_ok": animaux,
    "publie_par": publie_par,
    "annee_construction": annee_construction,
    "livre": livre,
    "promoteur": promoteur,
    "duree_min_mois": duree_min_location,
    "landmark": landmark,
    "unite_ref": unite_ref,
}


# Type SQL de chaque champ, declare UNE SEULE FOIS ici. Les stores et le backfill
# en derivent au lieu de tenir leur propre liste : trois listes tenues a la main,
# c'est trois occasions de diverger — le meme piege que median_price (moyenne en
# SQLite, mediane en Postgres) corrige le 2026-07-28.
_TYPES = {"etage": "integer", "vues_n": "integer", "animaux_ok": "integer",
          "annee_construction": "integer", "duree_min_mois": "integer",
          "livre": "integer",
          "cam_fee_thb": "real", "elec_kwh": "real", "eau_m3": "real"}

#: [(nom de colonne, type SQL)] pour les 20 champs, dans l'ordre de CHAMPS.
COLONNES = tuple((f"d_{c}", _TYPES.get(c, "text")) for c in CHAMPS)


def extraire(description: str, area_sqm: float | None = None) -> dict:
    """`area_sqm` permet a cam_fee() de convertir un tarif au m2 et de juger la
    vraisemblance. Sans elle, les charges aberrantes passent."""
    t = re.sub(r"\s+", " ", description or "")
    out = {}
    for nom, f in CHAMPS.items():
        out[nom] = f(t, area_sqm) if nom == "cam_fee_thb" else f(t)
    return out

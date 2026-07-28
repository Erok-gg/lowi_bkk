"""photo_sig.py — empreinte photo d'une annonce, sans télécharger les images.

PRINCIPE. Un agent qui republie une annonce (suppression puis reparution sous un
nouvel identifiant) réutilise les MÊMES fichiers image. Leur poids en octets est
donc un identifiant de lot beaucoup plus fiable que l'URL ou l'identifiant de
l'annonce. On relève ce poids par requête HEAD (`Content-Length`) : aucun octet
transféré, aucun stockage — la couverture reste la seule image téléchargée.

Le nombre de photos est enregistré à part : deux annonces peuvent publier un
nombre différent de photos du même lot (l'agent en ajoute ou en retire). Une
correspondance sur les POIDS reste alors valable même si les comptes diffèrent —
c'est justement ce cas qui signe un repost déguisé.
"""
from __future__ import annotations

#: Tolérance sur le poids d'un fichier. Deux fichiers dont les tailles diffèrent
#: de moins de 10 % sont considérés comme le même (recompression, variante de
#: taille servie par le CDN).
TOLERANCE = 0.10

#: Au-delà, on n'interroge pas : l'empreinte est déjà discriminante et on ne
#: veut pas allonger le scan.
MAX_PHOTOS = 8


def relever(fetcher, urls: list[str]) -> tuple[int, list[int]]:
    """(nombre de photos annoncées, poids relevés triés) — sans téléchargement."""
    if not urls:
        return 0, []
    tailles = []
    for u in urls[:MAX_PHOTOS]:
        t = fetcher.head_size(u)
        if t and t > 1024:  # ignore les vignettes/pixels de suivi
            tailles.append(t)
    return len(urls), sorted(tailles)


def correspondent(a: list[int], b: list[int], tolerance: float = TOLERANCE) -> float:
    """Part des photos de `a` retrouvées dans `b` (appariement au plus proche).

    Retourne 0..1. Un seuil de 0,6 sur au moins 2 photos communes est un
    indice solide de même lot ; sur une seule photo, l'indice est faible car
    deux fichiers sans rapport peuvent se ressembler en taille.
    """
    if not a or not b:
        return 0.0
    restant = list(b)
    trouves = 0
    for ta in a:
        for i, tb in enumerate(restant):
            if abs(ta - tb) <= tolerance * max(ta, tb):
                trouves += 1
                restant.pop(i)
                break
    return trouves / len(a)


def est_doublon(sig_a: dict, sig_b: dict) -> tuple[bool, str]:
    """Deux annonces décrivent-elles le même lot, d'après leurs photos ?

    `sig_*` : {"photo_count": int, "photo_sizes": [int, ...]}
    Retourne (verdict, motif lisible).
    """
    a = sig_a.get("photo_sizes") or []
    b = sig_b.get("photo_sizes") or []
    if len(a) < 2 or len(b) < 2:
        return False, "empreinte trop courte (< 2 photos relevées)"

    part = correspondent(a, b)
    communes = round(part * len(a))
    if communes < 2:
        return False, f"{communes} photo(s) commune(s)"

    ca, cb = sig_a.get("photo_count"), sig_b.get("photo_count")
    if ca and cb and ca != cb:
        # Cas explicitement visé : le nombre change mais les fichiers sont les
        # mêmes → l'agent a ajouté ou retiré des vues du même lot.
        return True, f"{communes} photos identiques malgré {ca} vs {cb} photos"
    return part >= 0.6, f"{communes}/{len(a)} photos identiques"

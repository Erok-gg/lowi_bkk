"""Tests unitaires de l'extracteur — ecrits en FICHIER, pas en ligne de commande :
l'echappement du shell corrompait les regex et rendait les resultats ininterpretables.
"""
from pipeline.details import etage, vues, promoteur, cam_fee, meuble, quota, annee_construction

CAS = [
    # (fonction, texte, attendu, pourquoi)
    (etage, "Floor 7 Bedroom Studio Size 24 SqM", 7,
     "valeur normale : Floor puis le numero"),
    (etage, "Floor 2-Bedroom Condo at Life Asoke Rama 9 Discover this", None,
     "FAUX POSITIF reel : Floor suivi d'un TITRE, le 2 vient de 2-Bedroom"),
    (etage, "located on the 11th floor, at Supalai Premier", 11,
     "forme en prose (PropertyScout)"),

    (vues, "View(s) Skyline View, City View Unit Type N/A", ["Skyline View", "City View"],
     "liste COMPLETE, pas seulement la premiere"),
    (vues, "View(s) N/A Unit Type N/A", None,
     "la source ecrit N/A au lieu d'omettre"),
    (vues, "View(s) City View Unit Type N/A Building N/A", ["City View"],
     "vue unique"),

    (promoteur, "Developer: N/A Construction: Completed", None, "N/A n'est pas un nom"),
    (promoteur, "Developer: AP (Thailand) Construction: Completed", "AP (Thailand)",
     "nom reel"),

    (cam_fee, "CAM Fee The common area maintenance (CAM) fee has to be paid monthly "
              "by owners for the upkeep of the common areas. ฿2,160/mo Listed By", 2160.0,
     "valeur separee du libelle par un texte explicatif"),

    (meuble, "Furniture A fully-furnished property is one which is equipped with all "
             "required items of a household. Fully Furnished View(s)", "fully furnished",
     "idem : le libelle est suivi d'une definition avant la valeur"),

    (quota, "Thai Quota Furniture A fully-furnished", "thai", "quota thai"),
    (quota, "Foreign Quota Furniture", "foreigner", "quota etranger"),

    (annee_construction, "Construction: Completed (Apr 2020) Floors: 43", 2020,
     "forme FazWaz"),
    (annee_construction, "Building completed in 1990 Covered car park", 1990,
     "forme PropertyScout"),
]

if __name__ == "__main__":
    ok = 0
    for f, texte, attendu, pourquoi in CAS:
        obtenu = f(texte)
        bon = obtenu == attendu
        ok += bon
        print(f"  {'OK ' if bon else 'NON'} {f.__name__:20s} attendu={str(attendu)[:32]:34s}"
              f"obtenu={str(obtenu)[:32]}")
        if not bon:
            print(f"      ({pourquoi})")
    print(f"\n  {ok}/{len(CAS)}")

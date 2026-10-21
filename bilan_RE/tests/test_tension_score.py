"""test_tension_score.py — le score de tension tient-il ce qu'il promet ?

POURQUOI CE TEST EXISTE
Le score est fait à 95 % de code, sans relecture humaine à chaque bilan. Chaque
essai ci-dessous verrouille une propriété dont l'absence a déjà coûté une mesure
fausse sur ce dépôt :
  · une republication ne doit pas compter comme une vente (72 % des retraits
    DDproperty en étaient, mesuré le 2026-10-17) ;
  · une source en panne doit être écartée, pas lue comme un marché qui gèle
    (DDproperty à l'arrêt depuis le 13/10, Nestopa sans aucun retrait) ;
  · la durée de vente doit tenir compte des biens encore en vente (censure),
    sinon elle est courte par construction ;
  · deux exécutions sur les mêmes données donnent le même intervalle.
Données synthétiques uniquement : aucune base, aucun réseau.

Rejeu :  scraper/.venv/Scripts/python.exe bilan_RE/tests/test_tension_score.py
"""
import copy
import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bilan_RE.tension import coeur, liquidite, prix   # noqa: E402
from bilan_RE.tension.donnees import Calcul, config, sante   # noqa: E402

essais = 0
sys.stdout.reconfigure(encoding="utf-8")   # console Windows en cp1252


def verifie(nom: str, condition: bool, detail: str = "") -> None:
    global essais
    essais += 1
    if not condition:
        print(f"ÉCHEC — {nom} {detail}")
        sys.exit(1)
    print(f"ok  {nom} {detail}")


T1 = date(2026, 10, 12)
CFG = config()
CFG = {**CFG, "fiable_depuis": "2026-09-14", "bootstrap": {"tirages": 60, "graine": 7}}


def annonce(i, *, condo="A", khet="K1", ch=2, surf=50.0, debut, fin=None, src="s1",
            prix=None, lat=13.73, lng=100.56):
    uk = f"{condo}|{ch}|{int(surf // 5) * 5}|sale"
    return coeur.Annonce(id=str(i), source=src, unit_key=uk, condo=condo, khet=khet,
                         chambres=ch, surface=surf, lat=lat, lng=lng, debut=debut, fin=fin,
                         prix=prix or [(debut, surf * 100_000.0)])   # 100 k THB/m², réaliste


def marche(rng, n_condos=40, khet="K1", taux_sortie=0.08, src="s1", decal=0, lat=13.73):
    """Marché synthétique : chaque immeuble a 3 cohortes, une part sort pendant
    la fenêtre, le reste reste en vente."""
    out, i = [], decal
    for k in range(n_condos):
        for j in range(3):
            i += 1
            debut = T1 - timedelta(days=rng.randint(40, 400))
            sort = rng.random() < taux_sortie * 28 / 30
            fin = T1 - timedelta(days=rng.randint(1, 27)) if sort else None
            out.append(annonce(i, condo=f"{khet}-C{k}", khet=khet, surf=30 + 10 * j,
                               debut=debut, fin=fin, src=src, lat=lat + k * 0.001))
    return out


def main():
    rng = random.Random(1)

    # 1. Kaplan-Meier, cas calculé à la main. 4 cohortes entrées à 0 :
    #    sorties à 10 et 20, deux censurées à 30. S(10)=3/4, S(20)=3/4·2/3=1/2
    #    → médiane = 20. Sur les seules sorties on aurait obtenu 15.
    km = coeur.kaplan_meier_mediane([(0, 10, True), (0, 20, True), (0, 30, False), (0, 30, False)])
    verifie("Kaplan-Meier : médiane 20 (et pas 15)", km == 20, f"→ {km}")
    verifie("Kaplan-Meier : survie jamais sous 0,5 → None",
            coeur.kaplan_meier_mediane([(0, 10, True), (0, 30, False), (0, 30, False)]) is None)
    #    Troncature à gauche : une cohorte entrée à 25 n'est pas à risque à 10.
    #    À 10 : 2 à risque, 1 sortie → S = 1/2 → médiane 10. Si on la comptait
    #    à risque dès 0, on aurait S(10) = 2/3 puis S(30) = 1/3 → médiane 30.
    km2 = coeur.kaplan_meier_mediane([(0, 10, True), (25, 40, False), (0, 30, True)])
    verifie("Kaplan-Meier : entrée retardée hors du risque avant son entrée", km2 == 10, f"→ {km2}")

    # 2. Une republication n'est pas une sortie : même cohorte, retrait à J−10
    #    et nouvelle annonce à J−8 (identifiant différent).
    base = [annonce(1, debut=T1 - timedelta(days=200), fin=T1 - timedelta(days=10)),
            annonce(2, debut=T1 - timedelta(days=8))]
    f = coeur.faits(coeur.cohortes(base)[0], T1, CFG)
    verifie("republication dans la fenêtre : pas une sortie", f.a_risque and not f.sortie)
    #    Republiée APRÈS la fin de fenêtre, dans le délai de grâce : pas une sortie non plus.
    apres = [annonce(1, debut=T1 - timedelta(days=200), fin=T1 - timedelta(days=3)),
             annonce(2, debut=T1 + timedelta(days=5))]
    f = coeur.faits(coeur.cohortes(apres)[0], T1, CFG)
    verifie("republication dans la grâce : pas une sortie", not f.sortie)
    seule = [annonce(1, debut=T1 - timedelta(days=200), fin=T1 - timedelta(days=3))]
    verifie("vraie sortie : comptée", coeur.faits(coeur.cohortes(seule)[0], T1, CFG).sortie)

    # 3. Invariance du score aux republications : dupliquer chaque sortie en
    #    retrait + réapparition change les annonces, pas les cohortes vivantes.
    #    (7 districts : la référence exige au moins 5 khets publiables)
    m = sum((marche(random.Random(20 + j), khet=f"M{j}", taux_sortie=0.04 + 0.02 * j,
                    decal=200_000 * (j + 1)) for j in range(7)), [])
    calc = Calcul(T1, CFG, annonces=m)
    ref = calc.reference(None, None)
    s1, _ = coeur.score(coeur.signaux(calc._fs(calc.cohortes), CFG), ref, CFG)
    bruit, i = [], 10_000
    for a in m:
        if a.fin is None and rng.random() < 0.3:      # un agent qui republie un bien en vente
            i += 1
            r = copy.copy(a)
            a2 = copy.copy(a)
            r.fin = T1 - timedelta(days=15)
            a2.id, a2.debut = str(i), T1 - timedelta(days=14)
            bruit += [r, a2]
        else:
            bruit.append(a)
    calc2 = Calcul(T1, CFG, annonces=bruit)
    s2, _ = coeur.score(coeur.signaux(calc2._fs(calc2.cohortes), CFG), ref, CFG)
    verifie("score insensible aux republications", abs(s1 - s2) < 1e-9, f"{s1:.2f} vs {s2:.2f}")

    # 4. Normalisation : la médiane de référence vaut 50, l'ordre est respecté,
    #    le sens est appliqué, aucune dispersion → 50.
    r = (0.08, 0.02)
    verifie("note = 50 à la médiane", abs(coeur.note(0.08, r, +1, 3) - 50) < 1e-9)
    verifie("note monotone et orientée",
            coeur.note(0.12, r, +1, 3) > 50 > coeur.note(0.12, r, -1, 3))
    verifie("note bornée", coeur.note(99, r, +1, 3) < 100)
    verifie("aucune dispersion → 50", coeur.note(1, (0.08, None), +1, 3) == 50)

    # 5. Retour vers la moyenne : n=0 hérite du parent, n grand garde sa valeur.
    par = {s: 1.0 for s in coeur.SENS}
    v = coeur.retour_moyenne({"n": 0, **{s: None for s in coeur.SENS}}, par, 20)
    verifie("maille vide : hérite du parent", v["ecoulement"] == 1.0)
    v = coeur.retour_moyenne({"n": 20, **{s: 0.0 for s in coeur.SENS}}, par, 20)
    verifie("n = k : mi-chemin", abs(v["ecoulement"] - 0.5) < 1e-9)
    v = coeur.retour_moyenne({"n": 100_000, **{s: 0.0 for s in coeur.SENS}}, par, 20)
    verifie("n grand : garde sa valeur", v["ecoulement"] < 0.001)

    # 6. Un marché qui s'écoule plus vite note plus haut qu'un marché lent.
    rapide = marche(random.Random(2), khet="K1", n_condos=100, taux_sortie=0.20)
    lent = marche(random.Random(3), khet="K2", n_condos=100, taux_sortie=0.06, decal=50_000)
    autres = sum((marche(random.Random(10 + j), khet=f"R{j}", n_condos=100,
                         taux_sortie=0.08 + 0.02 * j, decal=100_000 * (j + 1)) for j in range(6)), [])
    calc = Calcul(T1, CFG, annonces=rapide + lent + autres)
    ref = calc.reference(None, None)
    sr = coeur.evaluer(calc._fs(coeur.filtre(calc.cohortes, ("khet", "K1"))), None, ref, CFG)
    sl = coeur.evaluer(calc._fs(coeur.filtre(calc.cohortes, ("khet", "K2"))), None, ref, CFG)
    verifie("rapide > lent", sr["score"] > sl["score"], f"{sr['score']} vs {sl['score']}")

    # 7. Bootstrap déterministe et intervalle cohérent.
    sr2 = coeur.evaluer(calc._fs(coeur.filtre(calc.cohortes, ("khet", "K1"))), None, ref, CFG)
    verifie("même graine → même intervalle", (sr["p10"], sr["p90"]) == (sr2["p10"], sr2["p90"]))
    verifie("p10 ≤ score ≤ p90", sr["p10"] <= sr["score"] <= sr["p90"],
            f"{sr['p10']} ≤ {sr['score']} ≤ {sr['p90']}")

    # 8. Petit échantillon : affiché, jamais noté.
    petit = coeur.evaluer(calc._fs(coeur.filtre(calc.cohortes, ("immeuble", "K1-C0"))), None, ref, CFG)
    verifie("sous le minimum : pas de score", petit["score"] is None
            and petit["libelle"] == "not enough data", f"n={petit['n_cohortes']}")

    # 9. Libellés : on n'affirme que si l'intervalle reste d'un côté du seuil.
    verifie("intervalle franc → buyer's", coeur.libelle(20, 25, 30, CFG) == "buyer's market")
    verifie("chevauche 35 → leaning", coeur.libelle(28, 32, 40, CFG) == "leaning buyer's")
    verifie("intervalle trop large → pas de verdict", coeur.libelle(10, 40, 60, CFG) == "not enough data")

    # 10. Signal absent : poids redistribués, total = 1.
    sig = {"n": 100, "sorties": 20, "ecoulement": 0.1, "duree": None, "offre": None,
           "baisses": 0.1, "momentum": None, "vendeurs": 2.0}
    refx = {s: (0.1, 0.05) for s in coeur.SENS}
    sc, det = coeur.score(sig, refx, CFG)
    verifie("poids redistribués sur les signaux présents",
            abs(sum(det["poids"].values()) - 1) < 1e-9 and set(det["poids"]) == {"ecoulement", "prix", "vendeurs"})

    # 11. Santé des sources : une source qui cesse de délister est écartée ;
    #     une source saine est gardée ; l'exclusion manuelle s'applique.
    saine = marche(random.Random(4), src="saine", n_condos=120)
    figee = [copy.copy(a) for a in marche(random.Random(5), src="figee", n_condos=120, decal=900_000)]
    for a in figee:                       # plus aucun retrait depuis J−8
        if a.fin and a.fin > T1 - timedelta(days=8):
            a.fin = None
    v = sante(saine + figee + [annonce(9, debut=T1 - timedelta(days=50), src="livinginsider")], T1, CFG)
    verifie("source saine gardée", v["saine"]["gardee"], str(v["saine"]["raisons"]))
    verifie("source figée écartée", not v["figee"]["gardee"], str(v["figee"]["raisons"]))
    verifie("exclusion manuelle appliquée", not v["livinginsider"]["gardee"])
    #     Le recensement (stock qui double) n'est pas lu comme un marché.
    recens = marche(random.Random(6), src="recens", n_condos=80, decal=950_000)
    recens += [annonce(990_000 + j, condo=f"N{j}", debut=T1 - timedelta(days=5), src="recens")
               for j in range(300)]
    verifie("recensement écarté", not sante(recens, T1, CFG)["recens"]["gardee"])
    #     Forçage : gardée jusqu'à sa date, garde-fou réarmé au-delà.
    cfg_f = copy.deepcopy(CFG)
    cfg_f["sante_sources"]["saines_forcees"] = [
        {"source": "figee", "jusqu_au": T1.isoformat(), "raison": "test"}]
    vf = sante(saine + figee, T1, cfg_f)["figee"]
    verifie("forçage : source figée gardée, raison tracée", vf["gardee"] and vf["raisons"], str(vf))
    cfg_f["sante_sources"]["saines_forcees"][0]["jusqu_au"] = (T1 - timedelta(days=1)).isoformat()
    verifie("forçage expiré : garde-fou réarmé", not sante(saine + figee, T1, cfg_f)["figee"]["gardee"])

    # 12. Rayon : 1 km autour d'un point garde le voisin à 500 m, pas celui à 3 km.
    cs = coeur.cohortes([annonce(1, condo="P", debut=T1, lat=13.7300, lng=100.5600),
                         annonce(2, condo="Q", debut=T1, lat=13.7345, lng=100.5600),
                         annonce(3, condo="R", debut=T1, lat=13.7570, lng=100.5600)])
    gardes = {c.condo for c in coeur.filtre(cs, ("rayon", 13.73, 100.56, 1.0))}
    verifie("rayon de 1 km", gardes == {"P", "Q"}, str(sorted(gardes)))
    #     Surface ±15 % autour de 50 m² : 44 gardé, 40 écarté.
    cs = coeur.cohortes([annonce(1, condo="S", surf=44, debut=T1), annonce(2, condo="T", surf=40, debut=T1)])
    verifie("surface ±15 %", {c.condo for c in coeur.filtre(cs, ("tout",), surface=(50, 0.15))} == {"S"})

    # ─────────────────────────── liquidité ─────────────────────────────────────
    # 13. Postulat « revente au prix du marché » : des cohortes affichées 60 % au-
    #     dessus de leur immeuble (20 M pour 95 m² ≈ 210 k/m², contre 100 k/m²), qui
    #     ne partent jamais, ne ralentissent pas la vitesse.
    vite = sum((marche(random.Random(30 + j), khet=f"L{j}", n_condos=100, taux_sortie=0.10 + 0.03 * j,
                       decal=3_000_000 + 100_000 * j) for j in range(7)), [])
    calc = Calcul(T1, CFG, annonces=vite)
    v0 = liquidite.signaux(calc._fs(coeur.filtre(calc.cohortes, ("khet", "L0"))), CFG)["vitesse"]
    trop_cher = [annonce(4_000_000 + j, condo=f"L0-C{j}", khet="L0", surf=95.0,
                         debut=T1 - timedelta(days=300), prix=[(T1 - timedelta(days=300), 20_000_000.0)])
                 for j in range(60)]
    calc2 = Calcul(T1, CFG, annonces=vite + trop_cher)
    fs2 = calc2._fs(coeur.filtre(calc2.cohortes, ("khet", "L0")))
    v1 = liquidite.signaux(fs2, CFG)["vitesse"]
    verifie("annonces surévaluées sans effet sur la vitesse", v0 == v1, f"{v0} vs {v1}")
    kept = liquidite.au_prix_du_marche(fs2, 0.10)
    verifie("surévaluées écartées du périmètre « marché »",
            not any(f.prix_m2 and f.prix_m2 > 190_000 for f in kept))

    # 14. Un district qui s'écoule vite est plus liquide qu'un lent.
    ref = calc.reference(None, None, liquidite.LIQUIDITE)
    lq_vite = coeur.evaluer(calc._fs(coeur.filtre(calc.cohortes, ("khet", "L6"))), None, ref, CFG,
                            liquidite.LIQUIDITE)
    lq_lent = coeur.evaluer(calc._fs(coeur.filtre(calc.cohortes, ("khet", "L0"))), None, ref, CFG,
                            liquidite.LIQUIDITE)
    # (un score de 0 est un vrai score : jamais de `or` sur une valeur numérique)
    verifie("liquidité : rapide > lent", lq_vite["score"] is not None and lq_lent["score"] is not None
            and lq_vite["score"] > lq_lent["score"],
            f"{lq_vite['score']} vs {lq_lent['score']} ({lq_vite['libelle']} / {lq_lent['libelle']})")

    # 15. Projection : si les immeubles plus vieux mettent 2× plus de temps à
    #     partir, le score projeté baisse ; sans âge connu, aucune projection.
    courbe = {"5-10": {"vitesse": 100.0, "vente90": 0.6}, "15-20": {"vitesse": 200.0, "vente90": 0.3}}
    sig = {"n": 100, "sorties": 20, "vitesse": 100.0, "vente90": 0.6, "profondeur": 2.0}
    refl = {"vitesse": (100.0, 30.0), "vente90": (0.6, 0.1), "profondeur": (2.0, 0.5)}
    cfg_p = {**CFG, "liquidite": {**CFG["liquidite"], "horizons_ans": [10],
                                  "jalons_travaux": [{"age": 15, "libelle": "test", "source": "test"}]}}
    pr = liquidite.projeter(sig, 7, courbe, refl, cfg_p)[0]
    s_now, _ = coeur.score(sig, refl, cfg_p, liquidite.LIQUIDITE)
    verifie("projection : immeuble qui vieillit → moins liquide", pr["score"] < s_now,
            f"{round(s_now)} → {pr['score']}, rapport {pr['rapport_vitesse']:.1f}")
    verifie("projection : jalon de travaux affiché, pas compté", pr["jalons"] and pr["jalons"][0]["age"] == 15)
    verifie("projection sans âge : refusée", liquidite.projeter(sig, None, courbe, refl, cfg_p)[0]["score"] is None)
    verifie("tranches d'âge", liquidite.tranche(7, [0, 5, 10, 15, 20, 30]) == "5-10"
            and liquidite.tranche(42, [0, 5, 10, 15, 20, 30]) == "30+")

    # ───────────────────────────── prix ────────────────────────────────────────
    # 16. Rang et verdict sur des comparables connus.
    fx = [coeur.Faits(condo="X", a_risque=True, sortie=False, entree=0, age_fin=10, active_fin=True,
                      active_recul=True, baisse=False, ratio_prix=None, prix_m2=float(p))
          for p in (100, 110, 120, 130, 140, 150, 160, 170)]
    r = prix.comparer(165.0, fx)
    verifie("prix : 7 comparables sur 8 moins chers → 88 %", r["rang_pct"] == 88, str(r["rang_pct"]))
    verifie("prix : au-dessus du 3e quartile", r["verdict"] == "above most comparables")
    verifie("prix : moins de 5 comparables → pas de verdict",
            prix.comparer(120.0, fx[:4])["verdict"] == "not enough comparables")

    print(f"\nTOUS LES ESSAIS PASSENT ({essais})")


if __name__ == "__main__":
    main()

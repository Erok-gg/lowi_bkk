/**
 * Résolveur de condos : rapproche les noms d'immeubles extraits des annonces
 * Facebook des ~3 700 condos déjà connus dans la base Lowi_bkk.
 *
 * Pourquoi c'est la brique centrale : une fois l'immeuble reconnu, on hérite
 * gratuitement de ses coordonnées GPS, de son quartier (khet) et surtout de la
 * MÉDIANE DE PRIX de ses annonces — ce qui permet de dire si une annonce
 * Facebook est au marché, au-dessus, ou une opportunité.
 *
 * Le rapprochement est fait par le CODE (normalisation + distance d'édition),
 * pas par le modèle : c'est une comparaison exacte, pas un jugement.
 *
 * Usage : node immo-resolve.mjs [fichier_extrait.json]
 */
import { readFileSync, writeFileSync } from "fs";
import { execFileSync } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const file = process.argv[2] ?? "../output/social/immo_facebook_2026-07-25_extrait.json";
// Référence depuis la bascule du 2026-08-25 (commit cea4938) : scraper/output/bangkok.db,
// pas archive/lowi-archive.db — celle-ci n'existe même plus sur ce poste (PC2), et même
// quand elle existe elle retarde sur le dernier scrap. Cf. CLAUDE.md § Architecture des données.
const REFERENCE_DB = join(dirname(fileURLToPath(import.meta.url)), "..", "output", "bangkok.db");
// Python du venv du scraper, pas "python" du PATH : sur PC2 ce nom est le
// raccourci Microsoft Store ("Python est introuvable"), mesuré le 2026-09-13.
const PYTHON = process.env.LOWI_PY || join(dirname(fileURLToPath(import.meta.url)), "..", ".venv", "Scripts", "python.exe");

// ─── Référentiel : les condos connus de Lowi_bkk ────────────────────────────
// Lecture SEULE de la base de référence (aucune écriture, aucun impact sur le scrap en cours).
function chargerReferentiel() {
  const py = `
import sqlite3, json
from collections import defaultdict
c = sqlite3.connect('file:${REFERENCE_DB.replace(/\\/g, "/")}?mode=ro', uri=True)
# UNE passe sur la table, agrégée en Python. La version d'avant faisait 3
# requêtes PAR condo (8 165 condos × 3 balayages de listings sans index sur
# condo_name) : sur la base de 2,5 Go de PC2 elle dépassait 10 minutes,
# mesuré le 2026-09-13. Ici : ~2 s pour 126 244 lignes.
acc = defaultdict(lambda: {'khet': None, 'n': 0, 'lat': [], 'lng': [],
                           'sale': [], 'rent': [], 'ppsqm': []})
for name, khet, deal, price, ppsqm, lat, lng in c.execute('''
  select condo_name, khet, deal_type, price, price_per_sqm, lat, lng
  from listings where condo_name is not null and trim(condo_name) <> ''
'''):
    a = acc[name]
    a['n'] += 1
    if khet and not a['khet']: a['khet'] = khet
    if lat is not None: a['lat'].append(lat)
    if lng is not None: a['lng'].append(lng)
    if price and price > 0:
        a['sale' if deal == 'sale' else 'rent'].append(price)
        if deal == 'sale' and ppsqm and ppsqm > 0: a['ppsqm'].append(ppsqm)
def med(v):
    v = sorted(v); return v[len(v)//2] if v else None
out = []
for name, a in acc.items():
    out.append({'nom': name, 'khet': a['khet'], 'n': a['n'],
                'lat': sum(a['lat'])/len(a['lat']) if a['lat'] else None,
                'lng': sum(a['lng'])/len(a['lng']) if a['lng'] else None,
                'n_sale': len(a['sale']), 'n_rent': len(a['rent']),
                'med_vente': med(a['sale']), 'med_loyer': med(a['rent']),
                'med_prix_m2_vente': med(a['ppsqm'])})
print(json.dumps(out, ensure_ascii=False))
`;
  return JSON.parse(execFileSync(PYTHON, ["-c", py], { encoding: "utf-8", maxBuffer: 64 * 1024 * 1024,
    // sans ca, stdout Python est en cp1252 sous Windows : un espace insecable
    // (U+200B) dans un nom de condo faisait tout tomber (2026-09-13)
    env: { ...process.env, PYTHONIOENCODING: "utf-8" } }));
}

// ─── Normalisation des noms ─────────────────────────────────────────────────
// Les noms Lowi portent un suffixe ", Bangkok" ; les annonces Facebook écrivent
// en majuscules, avec des tirets fantaisistes, parfois le mot "condo" en trop.
function normaliser(s) {
  return (s ?? "")
    .normalize("NFC")
    .toLowerCase()
    .replace(/,\s*bangkok\s*$/i, "")
    .replace(/\b(condo(minium)?|project|residence[s]?|tower|building|for (rent|sale))\b/g, " ")
    .replace(/[–—−]/g, "-")
    .replace(/[^\p{L}\p{N}\s-]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Distance de Levenshtein normalisée (0 = identique, 1 = tout différent)
function similarite(a, b) {
  if (a === b) return 1;
  const m = a.length, n = b.length;
  if (!m || !n) return 0;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return 1 - prev[n] / Math.max(m, n);
}

const ref = chargerReferentiel();
const refNorm = ref.map((r) => ({ ...r, norm: normaliser(r.nom) }));
console.log(`Référentiel Lowi : ${ref.length} condos connus`);

const fiches = JSON.parse(readFileSync(file, "utf-8"));
const annonces = fiches.filter((f) => f.est_une_annonce && f.nom_immeuble);
console.log(`Annonces avec nom d'immeuble : ${annonces.length}\n`);

let exact = 0, approx = 0, aucun = 0;
for (const a of annonces) {
  const n = normaliser(a.nom_immeuble);
  if (!n) { aucun++; continue; }

  // 1. correspondance exacte après normalisation
  let best = refNorm.find((r) => r.norm === n);
  let score = best ? 1 : 0;

  // 2. sinon, meilleure similarité (seuil prudent : 0,86)
  if (!best) {
    for (const r of refNorm) {
      // pré-filtre bon marché : longueurs comparables
      if (Math.abs(r.norm.length - n.length) > Math.max(6, n.length * 0.4)) continue;
      const s = similarite(n, r.norm);
      if (s > score) { score = s; best = r; }
    }
    if (score < 0.86) best = null;
  }

  if (best) {
    a.condo_lowi = best.nom;
    a.condo_khet = best.khet;
    a.condo_lat = best.lat;
    a.condo_lng = best.lng;
    a.condo_med_loyer = best.med_loyer;
    a.condo_med_vente = best.med_vente;
    a.condo_nb_annonces = best.n;
    a.condo_score = Math.round(score * 100) / 100;
    // Écart au marché de l'immeuble : c'est le signal d'opportunité
    if (a.loyer_mensuel_thb > 0 && best.med_loyer) {
      a.ecart_loyer_pct = Math.round(((a.loyer_mensuel_thb - best.med_loyer) / best.med_loyer) * 100);
    }
    if (a.prix_vente_thb > 0 && best.med_vente) {
      a.ecart_vente_pct = Math.round(((a.prix_vente_thb - best.med_vente) / best.med_vente) * 100);
    }
    score === 1 ? exact++ : approx++;
  } else {
    aucun++;
  }
}

console.log(`Rapprochés exactement : ${exact}`);
console.log(`Rapprochés par similarité : ${approx}`);
console.log(`Non trouvés dans Lowi : ${aucun}`);
console.log(`→ taux de rapprochement : ${Math.round((100 * (exact + approx)) / Math.max(annonces.length, 1))} %\n`);

const avecEcart = annonces.filter((a) => a.ecart_loyer_pct !== undefined || a.ecart_vente_pct !== undefined);
if (avecEcart.length) {
  console.log("── Écarts au marché de l'immeuble (négatif = sous le marché) ──");
  avecEcart
    .sort((a, b) => (a.ecart_loyer_pct ?? a.ecart_vente_pct) - (b.ecart_loyer_pct ?? b.ecart_vente_pct))
    .slice(0, 12)
    .forEach((a) => {
      const e = a.ecart_loyer_pct ?? a.ecart_vente_pct;
      const t = a.ecart_loyer_pct !== undefined
        ? `loyer ${a.loyer_mensuel_thb}฿ vs médiane ${Math.round(a.condo_med_loyer)}฿`
        : `vente ${(a.prix_vente_thb / 1e6).toFixed(2)}M฿ vs médiane ${(a.condo_med_vente / 1e6).toFixed(2)}M฿`;
      console.log(`  ${String(e).padStart(5)}%  ${a.condo_lowi.slice(0, 38).padEnd(38)} ${t}`);
    });
}

const dest = file.replace(/\.json$/, "_resolu.json");
writeFileSync(dest, JSON.stringify(fiches, null, 2), "utf-8");
console.log(`\n✓ ${dest}`);

/**
 * types.ts — contrat du rapport JSON produit par `bilan_RE/tension/rapport.py`.
 * Toute modification du Python se reporte ici (et dans regles-construction-ui.md §4).
 */
export type Niveau = {
  score: number | null;
  p10: number | null;
  p90: number | null;
  libelle: string;
  n_cohortes: number;
  n_sorties: number;
};
export type Chaine = Record<string, Niveau>;

export type Comparaison = {
  cle: "building" | "building_same" | "radius_same" | "khet_same";
  niveau: string;
  n: number;
  verdict: string;
  mediane?: number;
  p25?: number;
  p75?: number;
  min?: number;
  max?: number;
  ecart?: number;
  rang_pct?: number;
  points?: number[];
  /** Valeurs aberrantes retirées de l'échantillon (au-delà de 3× / en deçà de 1/3 de la médiane). */
  exclus?: number;
};

export type Evenement = {
  date: string;
  type: "listed" | "price_cut" | "price_rise";
  source: string;
  /** Clé du portail (« fazwaz ») : sert à choisir le favicon local. */
  cle?: string;
  /** Lien vers l'annonce, seulement tant qu'elle est en ligne. */
  url?: string | null;
  from?: number;
  to?: number;
};

export type Bande = { n: number; mediane: number; p25: number; p75: number; points: number[]; propre: number | null };
export type Charges = {
  propre: number | null;
  equipements: string[];
  meme_prix: Bande | null;
  memes_equipements: Bande | null;
  n_immeubles_avec_charges: number;
};
export type SortiesPrix = {
  jours: number; tolerance: number; rayon_km: number; n_parties: number; n_actives: number;
  mediane_jours: number | null; part_30j: number | null;
};
export type PointStock = { mois: number; bas: number; haut: number; retraits: number; stock: number };
export type MoisDeStock = {
  fenetre_jours: number;
  points: { fin: string; bangkok: PointStock | null; immeuble: PointStock | null }[];
  immeuble_periode: (PointStock & { jours: number }) | null;
  officiel: { mois: number; absorption_mensuelle: number; periode: string; perimetre: string; source: string; url: string };
};

export type Rapport = {
  id: string;
  url: string;
  genere_le: string;
  /** « AAAA-MM-JJ HH:MM », heure du serveur. */
  demande_le?: string;
  statut: "ok" | "not_found";
  donnees_du?: string;
  annonce?: {
    id: string;
    source: string;
    condo: string;
    khet: string;
    chambres: number | null;
    sdb: number | null;
    surface: number;
    prix: number;
    prix_m2: number;
    etage: number | null;
    meuble: string | null;
    quota: "foreigner" | "thai" | null;
    active: boolean;
    titre: string | null;
  };
  histoire?: {
    premier_vu: string;
    jours_en_ligne: number;
    portails: string[];
    annonces: number;
    prix_initial: number;
    prix_actuel: number;
    variation: number | null;
    baisses: number;
    evenements: Evenement[];
  };
  prix?: Comparaison[];
  /** Ventes déclarées par un portail : SOURCE FAIBLE, toujours affichée étiquetée. */
  ventes_portail?: {
    fiabilite: "low";
    etiquette: string;
    note: string;
    n_immeuble: number;
    n_comparables: number;
    fenetre_mois: number;
    n_24_mois?: number;
    mediane_m2: number | null;
    ecart: number | null;
    ventes: { mois: string; surface: number | null; etage: string | null; prix_m2: number }[];
    resume: { n: number | null; prix_m2: number | null; jours_avant_vente: number | null;
              decote_pct: number | null; releve_le: string } | null;
  } | null;
  immeuble?: {
    lots_en_vente: number;
    /** Lots distincts vus à la vente par nos robots, tous statuts : jamais le total réel du bâtiment. */
    lots_recenses?: number;
    annee: number | null;
    charges_thb_m2: number | null;
    adresse?: string;
    charges?: Charges;
  };
  sorties_prix?: SortiesPrix | null;
  mois_de_stock?: MoisDeStock;
  tension?: { chaine: Chaine | null; retenu: (Niveau & { niveau: string }) | null } | null;
  liquidite?: { chaine: Chaine | null; retenu: (Niveau & { niveau: string }) | null } | null;
  scores_calcul?: {
    fin_fenetre: string | null;
    calcule_le: string | null;
    frequence_calcul: string | null;
    config_version: number | null;
    sources_gardees: string[] | null;
  };
  drapeaux?: { niveau: "high" | "medium" | "low"; texte: string }[];
  /** Calculés pour tous ; affichés seulement au profil « investisseur ». */
  loyer_estime?: LoyerEstime | null;
  renovation?: Renovation | null;
  /** Affiché quel que soit le profil. */
  frais_achat?: FraisAchat | null;
};

export type LoyerEstime =
  | { statut: "not enough comparables"; n_immeuble: number }
  | {
      statut: "ok";
      niveau: "building_same" | "building" | "radius_same";
      libelle: string;
      confiance: "high" | "medium" | "low";
      n: number;
      loyer_m2: number;
      loyer: number;
      fourchette: [number, number];
      rendement_brut: number | null;
      etage_lot: number | null;
      par_etage: { tranche: string; n: number; loyer: number | null }[];
      note: string;
    };

export type Renovation = {
  niveau: "building" | "radius";
  libelle: string;
  n: number;
  n_renovees: number;
  part: number;
  prime: number | null;
  n_immeubles: number;
  verdict: string;
};

export type FraisAchat = {
  base: number;
  lignes: {
    poste: string;
    taux: number | null;
    montant: number | null;
    montant_min?: number | null;
    montant_max?: number | null;
    payeur: "buyer" | "seller";
    note: string | null;
    etrangers_seulement: boolean;
    cas: "always" | "negotiated" | "mortgage" | "foreigner" | "new" | "optional";
  }[];
  total_acheteur: number;
  total_acheteur_pct: number;
  avertissement: string;
};

/** Profil choisi dans les menus de la page d'accueil (cookie `lowi_profil`). */
export type Profil = { but: "invest" | "live" | "sell"; nat: "foreigner" | "thai" };

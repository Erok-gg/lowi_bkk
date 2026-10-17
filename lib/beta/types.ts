/**
 * types.ts — contrat du rapport JSON produit par `study/tension/rapport.py`.
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
};

export type Evenement = {
  date: string;
  type: "listed" | "price_cut" | "price_rise";
  source: string;
  from?: number;
  to?: number;
};

export type Rapport = {
  id: string;
  url: string;
  genere_le: string;
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
  immeuble?: { lots_en_vente: number; annee: number | null; charges_thb_m2: number | null };
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
};

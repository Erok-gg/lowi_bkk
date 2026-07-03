"use client";

/**
 * SearchProvider — état partagé header ↔ carte.
 * Centralise le sélecteur deal (All/Buy/Rent), la recherche texte et les filtres
 * du bandeau carte (prix, chambres, distance métro). La carte (MapView) lit cet
 * état pour filtrer les pins ; le header et le bandeau l'écrivent. MapView fournit
 * en plus un `controller` (suggestions d'autocomplétion) consommé par le header.
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Suggestion = { val: string; kind: string };
export type DealFilter = "all" | "sale" | "rent";

/** Filtres du bandeau de la carte principale (champs libres). */
export interface MapFilters {
  priceMin?: number;
  priceMax?: number;
  beds?: number;
  metroMax?: number; // distance max au métro, en mètres
}

export interface SearchController {
  suggest: (query: string, deal: DealFilter) => Suggestion[]; // rues / condos / quartiers
}

interface Ctx {
  controller: SearchController | null;
  setController: (c: SearchController | null) => void;
  deal: DealFilter;
  setDeal: (d: DealFilter) => void;
  query: string;
  setQuery: (q: string) => void;
  mapFilters: MapFilters;
  setMapFilters: (f: MapFilters) => void;
}

const SearchContext = createContext<Ctx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [controller, setController] = useState<SearchController | null>(null);
  const [deal, setDeal] = useState<DealFilter>("all");
  const [query, setQuery] = useState("");
  const [mapFilters, setMapFilters] = useState<MapFilters>({});

  const value = useMemo(
    () => ({ controller, setController, deal, setDeal, query, setQuery, mapFilters, setMapFilters }),
    [controller, deal, query, mapFilters]
  );
  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useSearch() {
  return useContext(SearchContext);
}

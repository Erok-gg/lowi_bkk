"use client";

/**
 * SearchProvider — pont header ↔ carte pour la recherche.
 * La carte (MapView) enregistre un "controller" (run + suggest) ; le header
 * (barre centrée dans la nav) le consomme pour filtrer les pins et proposer des
 * suggestions. Découple l'UI de recherche de la logique carte.
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Suggestion = { val: string; kind: string };

export interface SearchController {
  run: (query: string) => void; // filtre les pins + recadre la carte
  suggest: (query: string) => Suggestion[]; // rues / condos / quartiers
}

interface Ctx {
  controller: SearchController | null;
  setController: (c: SearchController | null) => void;
}

const SearchContext = createContext<Ctx | null>(null);

export function SearchProvider({ children }: { children: ReactNode }) {
  const [controller, setController] = useState<SearchController | null>(null);
  // setController (setter useState) est stable → enregistrement unique côté carte.
  const value = useMemo(() => ({ controller, setController }), [controller]);
  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useSearch() {
  return useContext(SearchContext);
}

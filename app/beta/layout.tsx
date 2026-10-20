/**
 * Layout du produit — porte le thème « Ledger » (vert / or / blanc).
 *
 * Le thème n'est PAS global : la carte, les tableaux et les rendements gardent
 * le dark violet/anthracite. Ici on pose une seule classe, `theme-ledger`, qui
 * redéfinit tous les jetons de couleur sur ce sous-arbre (`config/theme.ts`).
 * Retirer la classe suffit à revenir en arrière (règle 7).
 *
 * Le header est RENDU AU-DESSUS de ce layout (`app/layout.tsx`) : il pose la
 * même classe lui-même, à partir de l'URL — voir `components/LowiHeader.tsx`.
 */
export default function BetaLayout({ children }: { children: React.ReactNode }) {
  return <div className="theme-ledger h-full min-h-0">{children}</div>;
}

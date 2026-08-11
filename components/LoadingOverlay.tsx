/**
 * LoadingOverlay — overlay violet foncé (bg-surface/50) + logo "lowi" dont le
 * "o" tourne sur son axe vertical. Utilisé par app/loading.tsx (Next.js
 * affiche ce fallback pendant le chargement de n'importe quelle page).
 */
export default function LoadingOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface/50 backdrop-blur-sm">
      <div className="font-logo text-4xl text-gold" style={{ perspective: "300px" }}>
        <span>l</span>
        <span className="logo-spin-o">o</span>
        <span>wi</span>
      </div>
    </div>
  );
}

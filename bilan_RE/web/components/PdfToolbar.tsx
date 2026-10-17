"use client";
import { useEffect } from "react";

/** Barre écran seulement : ouvre la boîte d'impression une fois la page rendue. */
export default function PdfToolbar() {
  useEffect(() => {
    const t = setTimeout(() => window.print(), 600);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="sticky top-0 z-10 flex items-center justify-center gap-3 bg-[#16131f] px-4 py-3 text-sm text-white print:hidden">
      <span>Choose “Save as PDF” as the printer.</span>
      <button type="button" onClick={() => window.print()} className="rounded-lg bg-gold px-4 py-2 font-semibold text-[#16131f]">
        Save as PDF
      </button>
    </div>
  );
}

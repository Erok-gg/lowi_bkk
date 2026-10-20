import { notFound, redirect } from "next/navigation";
import { accesProduit, betaPublique } from "@/bilan_RE/web/lib/acces";
import { lire } from "@/bilan_RE/web/lib/rapport";
import Report from "@/bilan_RE/web/components/Report";
import PdfToolbar from "@/bilan_RE/web/components/PdfToolbar";
import { compteCourant } from "@/bilan_RE/web/lib/session";
import { comptesActives, possede } from "@/bilan_RE/web/lib/comptes";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Version imprimable : fond clair, tout déplié, explications incluses. Le PDF est
 *  produit par l'impression du navigateur (« Save as PDF ») : aucune dépendance
 *  serveur lourde pendant la beta (règles de construction §6).
 *
 *  QUI Y A DROIT. Tant que la beta est fermée (pas de `LOWI_BETA_PUBLIQUE`), le
 *  mot de passe partagé suffit : c'est toi qui regardes. Dès qu'elle est
 *  ouverte, il faut un compte à qui le rapport est rattaché — c'est ce que fait
 *  le bouton PDF (`/api/compte/rapport`).
 *  ⚠ On vérifie la POSSESSION, pas le paiement : `paye` reste à 0 partout tant
 *  qu'aucun prestataire n'est branché. Le jour où il l'est, la condition
 *  devient `paye === 1` ici et nulle part ailleurs. */
export default async function RapportPdf({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!(await accesProduit())) redirect(`/login?next=/beta/r/${id}/pdf`);

  if (betaPublique() && comptesActives()) {
    const compte = await compteCourant();
    if (!compte) redirect(`/beta/login`);
    if (!possede(compte.id, id)) redirect(`/beta/r/${id}`);
  }

  const r = lire(id);
  if (!r || r.statut !== "ok") notFound();
  return (
    <div className="h-full overflow-y-auto bg-sunken print:bg-white">
      <PdfToolbar />
      <div className="mx-auto my-6 max-w-[210mm] bg-white shadow-xl print:my-0 print:shadow-none">
        <Report r={r} mode="pdf" />
      </div>
    </div>
  );
}

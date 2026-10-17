import { notFound, redirect } from "next/navigation";
import { isAuthed } from "@/lib/auth";
import { lire } from "@/lib/beta/rapport";
import Report from "@/components/beta/Report";
import PdfToolbar from "@/components/beta/PdfToolbar";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Version imprimable : fond clair, tout déplié, explications incluses. Le PDF est
 *  produit par l'impression du navigateur (« Save as PDF ») : aucune dépendance
 *  serveur lourde pendant la beta (règles de construction §6). */
export default async function RapportPdf({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!(await isAuthed())) redirect(`/login?next=/beta/r/${id}/pdf`);
  const r = lire(id);
  if (!r || r.statut !== "ok") notFound();
  return (
    <div className="h-full overflow-y-auto bg-[#e9e6f0] print:bg-white">
      <PdfToolbar />
      <div className="mx-auto my-6 max-w-[210mm] bg-white shadow-xl print:my-0 print:shadow-none">
        <Report r={r} mode="pdf" />
      </div>
    </div>
  );
}

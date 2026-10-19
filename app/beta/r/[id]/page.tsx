import Link from "next/link";
import { redirect } from "next/navigation";
import { accesProduit } from "@/bilan_RE/web/lib/acces";
import { lire } from "@/bilan_RE/web/lib/rapport";
import Report from "@/bilan_RE/web/components/Report";
import { compteCourant } from "@/bilan_RE/web/lib/session";
import { possede } from "@/bilan_RE/web/lib/comptes";
import { langueCourante } from "@/bilan_RE/web/lib/langue";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function RapportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!(await accesProduit())) redirect(`/login?next=/beta/r/${id}`);
  const r = lire(id);
  if (!r || r.statut === "not_found")
    return (
      <div className="mx-auto max-w-xl px-4 pt-24 text-center">
        <h1 className="text-2xl font-semibold">{r ? "We could not find this listing" : "Report not found"}</h1>
        <p className="mt-3 text-text-muted">
          {r
            ? "It is not in our database yet: it may be very recent, or on a page we do not read. Try another listing."
            : "This report does not exist or is no longer available."}
        </p>
        <Link href="/beta" className="mt-8 inline-block rounded-xl bg-violet-fluo px-6 py-3 font-semibold text-white">
          Analyse another listing
        </Link>
      </div>
    );

  // Le bilan reste lisible sans compte (il est gratuit, backlog #1) ; c'est le
  // rapport complet en PDF qui demande l'e-mail. L'état du compte est résolu
  // ici parce que `Report` est un composant navigateur.
  const [compte, langue] = await Promise.all([compteCourant(), langueCourante()]);
  return (
    <Report
      r={r}
      acces={{
        langue,
        connecte: Boolean(compte),
        possede: Boolean(compte && possede(compte.id, id)),
      }}
    />
  );
}

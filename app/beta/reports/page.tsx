import Link from "next/link";
import { redirect } from "next/navigation";
import { rapportsDe } from "@/bilan_RE/web/lib/comptes";
import { compteCourant } from "@/bilan_RE/web/lib/session";
import { i18n } from "@/bilan_RE/web/lib/langue";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * « Mes rapports » — la page gardée dans l'app (demande du 2026-10-19, #25).
 * Chaque bilan acheté reste ici, réouvrable et téléchargeable, sans refaire le
 * calcul : l'identifiant est celui de l'URL de l'annonce, donc le JSON déjà
 * produit est retrouvé tel quel.
 */
export default async function MesRapports() {
  const compte = await compteCourant();
  if (!compte) redirect("/beta/login");
  const { t } = await i18n();
  const liste = rapportsDe(compte.id);

  return (
    <div className="h-full overflow-y-auto">
      <section className="mx-auto max-w-3xl px-4 pb-16 pt-10">
        <h1 className="text-2xl font-semibold text-text">{t("rep_title")}</h1>
        <p className="mt-1 text-sm text-text-faint">{compte.email_saisi ?? compte.email}</p>

        {liste.length === 0 ? (
          <p className="mt-8 text-sm text-text-muted">{t("rep_empty")}</p>
        ) : (
          <ul className="mt-6 divide-y divide-violet-soft overflow-hidden rounded-xl border border-violet-soft bg-surface">
            {liste.map((r) => (
              <li key={r.rapport_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-text">{r.titre ?? r.rapport_id}</p>
                  <p className="text-xs text-text-faint">
                    {r.cree_le.slice(0, 10)} · {r.paye ? t("rep_paid") : t("rep_free")}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Link
                    href={`/beta/r/${r.rapport_id}`}
                    className="rounded-md border border-violet-soft px-3 py-1.5 text-xs text-text transition hover:border-violet-fluo"
                  >
                    {t("rep_open")}
                  </Link>
                  <Link
                    href={`/beta/r/${r.rapport_id}/pdf`}
                    target="_blank"
                    rel="noopener"
                    className="rounded-md bg-gold px-3 py-1.5 text-xs font-semibold text-[#16131f]"
                  >
                    {t("rep_pdf")}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}

        <Link href="/beta" className="mt-8 inline-block text-sm text-gold underline">
          {t("rep_analyse_another")}
        </Link>
      </section>
    </div>
  );
}

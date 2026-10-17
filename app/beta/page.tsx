import { redirect } from "next/navigation";
import { isAuthed } from "@/lib/auth";
import AnalyseForm from "@/bilan_RE/web/components/AnalyseForm";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const POINTS = [
  { t: "Is the price right?", d: "Price per m² against the same building, the same beds and size, within 1 km." },
  { t: "Is the seller in a hurry?", d: "How long it has been listed, on how many portals, and every price cut." },
  { t: "Who has the upper hand?", d: "A buyer's-or-seller's market score out of 100, with the sample behind it." },
  { t: "Will it resell?", d: "How fast similar units sell at market price, and how that changes as the building ages." },
];

export default async function BetaPage() {
  if (!(await isAuthed())) redirect("/login?next=/beta");
  return (
    <div className="h-full overflow-y-auto">
      <section className="mx-auto flex max-w-3xl flex-col items-center px-4 pb-16 pt-14 text-center sm:pt-24">
        <span className="mb-6 rounded-full border border-gold/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-gold">
          Private beta
        </span>
        <h1 className="text-3xl font-semibold leading-tight text-text sm:text-5xl">
          Check a Bangkok condo <span className="text-violet-fluo">before</span> you make an offer.
        </h1>
        <p className="mt-5 max-w-xl text-base text-text-muted sm:text-lg">
          Paste the link of the listing. We compare it with what the market really offers, across five portals.
        </p>
        <div className="mt-10 w-full max-w-2xl text-left">
          <AnalyseForm />
          <p className="mt-3 text-center text-xs text-text-faint">
            Free summary · full report as PDF · Lowi takes nothing from the seller
          </p>
        </div>
      </section>
      <section className="mx-auto grid max-w-5xl gap-4 px-4 pb-20 sm:grid-cols-2 lg:grid-cols-4">
        {POINTS.map((p) => (
          <div key={p.t} className="rounded-2xl border border-violet-soft bg-surface p-5">
            <h2 className="text-base font-semibold text-text">{p.t}</h2>
            <p className="mt-2 text-sm text-text-muted">{p.d}</p>
          </div>
        ))}
      </section>
      <p className="mx-auto max-w-3xl px-4 pb-10 text-center text-xs text-text-faint">
        Based on asking prices and listing exits, not confirmed sales. Market scores are recalculated monthly.
        Not investment advice.
      </p>
    </div>
  );
}

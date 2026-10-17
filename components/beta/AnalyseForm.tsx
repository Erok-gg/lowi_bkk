"use client";
/**
 * AnalyseForm — le champ unique de la landing, puis l'écran de chargement.
 * Le chargement fait défiler ce qui est réellement calculé (pas un décor) ; il
 * dure au moins le temps d'un tour complet pour qu'on lise ce qui se passe, et
 * s'arrête dès que le serveur répond (règles de construction §5).
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AnalysisLoader from "./AnalysisLoader";

type Phase = { t: "idle" } | { t: "loading"; id: string } | { t: "error"; msg: string };

export default function AnalyseForm() {
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>({ t: "idle" });
  const router = useRouter();
  const debut = useRef(0);

  async function envoyer(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return setPhase({ t: "error", msg: "Paste the link of a listing first." });
    setPhase({ t: "loading", id: "" });
    debut.current = Date.now();
    const r = await fetch("/api/beta/analyse", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return setPhase({ t: "error", msg: j.erreur ?? "Something went wrong. Try again." });
    setPhase({ t: "loading", id: j.id });
  }

  useEffect(() => {
    if (phase.t !== "loading" || !phase.id) return;
    let fini = false;
    const tick = async () => {
      const j = await fetch(`/api/beta/analyse?id=${phase.id}`).then((r) => r.json()).catch(() => null);
      if (fini || !j) return;
      const assez = Date.now() - debut.current > 6500; // un tour de défilement lisible
      if ((j.etat === "ready" || j.etat === "not_found") && assez) {
        fini = true;
        router.push(`/beta/r/${phase.id}`);
      } else if (j.etat === "error") {
        fini = true;
        setPhase({ t: "error", msg: "The analysis failed on our side. Try again in a minute." });
      }
    };
    const h = setInterval(tick, 900);
    return () => {
      fini = true;
      clearInterval(h);
    };
  }, [phase, router]);

  if (phase.t === "loading") return <AnalysisLoader />;

  return (
    <form onSubmit={envoyer} className="w-full">
      <label htmlFor="url" className="sr-only">
        Link of the listing
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          id="url"
          type="url"
          inputMode="url"
          autoComplete="off"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            if (phase.t === "error") setPhase({ t: "idle" });
          }}
          placeholder="https://www.ddproperty.com/en/property/…"
          className="h-14 w-full rounded-xl border border-violet-soft bg-surface sm:flex-1 px-4 text-base text-text placeholder:text-text-faint focus:border-violet-fluo focus:outline-none focus:ring-2 focus:ring-violet-fluo/40"
        />
        <button
          type="submit"
          className="h-14 rounded-xl bg-violet-fluo px-7 text-base font-semibold text-white shadow-violet-glow transition hover:brightness-110 active:scale-[0.98]"
        >
          Analyse this listing
        </button>
      </div>
      {phase.t === "error" && (
        <p role="alert" className="mt-3 text-sm text-[#f87171]">
          {phase.msg}
        </p>
      )}
    </form>
  );
}

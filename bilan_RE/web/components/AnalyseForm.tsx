"use client";
/**
 * AnalyseForm — le champ unique de la landing, puis l'écran de chargement.
 * Le chargement fait défiler ce qui est réellement calculé (pas un décor) ; il
 * dure au moins le temps d'un tour complet pour qu'on lise ce qui se passe, et
 * s'arrête dès que le serveur répond (règles de construction §5).
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AnalysisLoader, { type Suivi } from "./AnalysisLoader";
import { traducteur, type Langue } from "../i18n";

type Phase = { t: "idle" } | { t: "loading"; id: string; s?: Suivi } | { t: "error"; msg: string };

export default function AnalyseForm({ langue = "en" }: { langue?: Langue }) {
  const t = traducteur(langue);
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>({ t: "idle" });
  const router = useRouter();
  const debut = useRef(0);

  async function envoyer(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return setPhase({ t: "error", msg: t("form_need_link") });
    // Profil des menus de la page d'accueil (s'ils existent sur la page) : lu par
    // le rapport et le PDF via le cookie, cf. lib/profil.ts. Un an, tout le site.
    const but = (document.getElementById("profil-but") as HTMLSelectElement | null)?.value;
    const nat = (document.getElementById("profil-nat") as HTMLSelectElement | null)?.value;
    if (but && nat) document.cookie = `lowi_profil=${but}|${nat}; path=/; max-age=31536000; samesite=lax`;
    setPhase({ t: "loading", id: "" });
    debut.current = Date.now();
    const r = await fetch("/api/beta/analyse", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return setPhase({ t: "error", msg: j.erreur ?? t("form_failed") });
    setPhase({ t: "loading", id: j.id, s: j });
  }

  useEffect(() => {
    if (phase.t !== "loading" || !phase.id) return;
    let fini = false;
    const tick = async () => {
      const j = await fetch(`/api/beta/analyse?id=${phase.id}`).then((r) => r.json()).catch(() => null);
      if (fini || !j) return;
      setPhase((p) => (p.t === "loading" ? { ...p, s: j } : p));
      const assez = Date.now() - debut.current > 6500; // un tour de défilement lisible
      if (j.etat === "not_found" && assez) {
        // portail reconnu mais annonce absente de la base : le prochain scrap l'ajoutera
        fini = true;
        setPhase({ t: "error", msg: "This listing is not in the database. Come back tomorrow at the same time, it will work." });
      } else if (j.etat === "ready" && assez) {
        fini = true;
        router.push(`/beta/r/${phase.id}`);
      } else if (j.etat === "error") {
        fini = true;
        setPhase({ t: "error", msg: "The analysis failed on our side. Try again in a minute." });
      } else if (j.etat === "unknown" && Date.now() - debut.current > 15000) {
        // la file vit en mémoire : un redémarrage du serveur la perd
        fini = true;
        setPhase({ t: "error", msg: "The server restarted and lost your request. Please submit it again." });
      }
    };
    const h = setInterval(tick, 900);
    return () => {
      fini = true;
      clearInterval(h);
    };
  }, [phase.t === "loading" ? phase.id : "", router]); // eslint-disable-line react-hooks/exhaustive-deps

  if (phase.t === "loading") return <AnalysisLoader s={phase.s} />;

  return (
    <form onSubmit={envoyer} noValidate className="w-full">
      <label htmlFor="url" className="sr-only">
        {t("form_label")}
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          id="url"
          type="text"
          inputMode="url"
          autoComplete="off"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            if (phase.t === "error") setPhase({ t: "idle" });
          }}
          placeholder="Paste your link here"
          className="h-14 w-full rounded-xl border border-rule bg-surface sm:flex-1 px-4 text-base text-ink placeholder:text-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/40"
        />
        <button
          type="submit"
          className="h-14 rounded-xl bg-brand px-7 text-base font-semibold text-white shadow-brand-glow transition hover:brightness-110 active:scale-[0.98]"
        >
          {t("form_cta")}
        </button>
      </div>
      {phase.t === "error" && (
        <p role="alert" className="mt-3 text-sm text-neg">
          {phase.msg}
        </p>
      )}
    </form>
  );
}

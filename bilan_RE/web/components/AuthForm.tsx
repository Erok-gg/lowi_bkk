"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { traducteur, type Langue } from "../i18n";

/**
 * AuthForm — connexion et inscription, le même composant.
 *
 * Inscription : UNIQUEMENT l'e-mail (décision du 2026-10-19). Le mot de passe
 * est généré par le serveur et envoyé par e-mail ; la personne n'en choisit pas
 * à la création, donc n'en réutilise pas un qu'elle a ailleurs. Nom, prénom,
 * date de naissance et nationalité seront demandés AU PAIEMENT — les colonnes
 * existent déjà, vides.
 */
export default function AuthForm({ langue, mode }: { langue: Langue; mode: "signin" | "signup" }) {
  const t = traducteur(langue);
  const router = useRouter();
  const inscription = mode === "signup";

  const [email, setEmail] = useState("");
  const [mdp, setMdp] = useState("");
  const [accepte, setAccepte] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [occupe, setOccupe] = useState(false);
  const [envoye, setEnvoye] = useState(false);
  const [oubli, setOubli] = useState(false);

  const messages: Record<string, string> = {
    bad_email: t("auth_bad_email"),
    consent_required: t("auth_consent_required"),
    bad_credentials: t("auth_bad"),
    accounts_unavailable: t("auth_unavailable"),
    too_many: t("auth_bad"),
  };

  async function soumets(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null);
    setOccupe(true);
    const route = inscription ? "/api/compte/inscription" : "/api/compte/connexion";
    const corps = inscription ? { email, langue, consentement: accepte } : { email, motDePasse: mdp };
    const r = await fetch(route, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(corps),
    }).catch(() => null);
    setOccupe(false);
    if (!r) return setErreur(t("auth_bad"));
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return setErreur(messages[j.erreur] ?? t("auth_bad"));
    if (inscription) {
      // Le mot de passe arrive par e-mail (file Gmail : quelques minutes), mais
      // la session est déjà ouverte : on ne fait pas attendre pour rien.
      setEnvoye(true);
      router.refresh();
    } else {
      router.push("/beta/reports");
      router.refresh();
    }
  }

  async function demandeOubli() {
    setOccupe(true);
    await fetch("/api/compte/oubli", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, langue }),
    }).catch(() => null);
    setOccupe(false);
    setOubli(true);
  }

  if (envoye)
    return (
      <div className="w-full max-w-sm rounded-xl border border-violet-soft bg-surface p-6">
        <h1 className="text-lg font-semibold text-text">{t("auth_sent_title")}</h1>
        <p className="mt-2 text-sm text-text-muted">{t("auth_sent_body", { email })}</p>
        <Link
          href="/beta/reports"
          className="mt-5 inline-block rounded-md bg-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-fluo"
        >
          {t("nav_reports")}
        </Link>
      </div>
    );

  return (
    <form onSubmit={soumets} className="w-full max-w-sm rounded-xl border border-violet-soft bg-surface p-6">
      <h1 className="text-lg font-semibold text-text">
        {inscription ? t("auth_signup_title") : t("auth_signin_title")}
      </h1>
      {inscription && <p className="mt-1 text-xs text-text-faint">{t("auth_signup_only_email")}</p>}

      <label className="mt-5 block text-xs uppercase tracking-wide text-text-faint" htmlFor="email">
        {t("auth_email")}
      </label>
      <input
        id="email"
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="mt-1 w-full rounded-md border border-violet-soft bg-anthracite-deep px-3 py-2 text-text outline-none focus:border-violet-fluo"
      />

      {!inscription && (
        <>
          <label className="mt-4 block text-xs uppercase tracking-wide text-text-faint" htmlFor="mdp">
            {t("auth_password")}
          </label>
          <input
            id="mdp"
            type="password"
            autoComplete="current-password"
            required
            value={mdp}
            onChange={(e) => setMdp(e.target.value)}
            className="mt-1 w-full rounded-md border border-violet-soft bg-anthracite-deep px-3 py-2 text-text outline-none focus:border-violet-fluo"
          />
        </>
      )}

      {inscription && (
        <label className="mt-4 flex items-start gap-2 text-xs text-text-muted">
          <input
            type="checkbox"
            checked={accepte}
            onChange={(e) => setAccepte(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-violet-fluo"
          />
          <span>
            {t("auth_consent", { privacy: "" })}{" "}
            <Link href="/beta/privacy" className="text-gold underline">
              {t("auth_privacy_link")}
            </Link>
          </span>
        </label>
      )}

      {erreur && <p className="mt-3 text-sm text-red-400">{erreur}</p>}
      {oubli && <p className="mt-3 text-sm text-text-muted">{t("auth_forgot_sent")}</p>}

      <button
        type="submit"
        disabled={occupe}
        className="mt-5 w-full rounded-md bg-violet px-3 py-2 font-medium text-white transition hover:bg-violet-fluo disabled:opacity-50"
      >
        {occupe ? "…" : inscription ? t("auth_signup_cta") : t("auth_signin_cta")}
      </button>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-text-faint">
        {inscription ? (
          <span>
            {t("auth_have_account")}{" "}
            <Link href="/beta/login" className="text-gold underline">
              {t("nav_signin")}
            </Link>
          </span>
        ) : (
          <>
            <span>
              {t("auth_no_account")}{" "}
              <Link href="/beta/signup" className="text-gold underline">
                {t("nav_signup")}
              </Link>
            </span>
            <button
              type="button"
              onClick={demandeOubli}
              disabled={!email || occupe}
              className="underline disabled:opacity-40"
            >
              {t("auth_forgot")}
            </button>
          </>
        )}
      </div>
    </form>
  );
}

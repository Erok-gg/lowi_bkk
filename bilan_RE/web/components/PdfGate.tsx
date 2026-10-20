"use client";

import Link from "next/link";
import { useState } from "react";
import { traducteur, type Langue } from "../i18n";

/**
 * PdfGate — le gros bouton PDF, et ce qu'il demande avant.
 *
 * Demande du 2026-10-19 : « quand on veut le pdf, ça demande l'e-mail de la
 * personne et ça lui crée un compte avec ce login ». Donc :
 *   · rapport déjà rattaché au compte → lien direct, aucune question ;
 *   · sinon → l'e-mail, une case pour la notice de confidentialité, et c'est
 *     tout. Le mot de passe est généré côté serveur et envoyé par e-mail.
 *
 * Le bouton garde EXACTEMENT l'apparence d'avant (même classe, même libellé en
 * anglais via le dictionnaire) : la porte s'ajoute, la disposition ne bouge pas
 * (règles de construction §6).
 */
export default function PdfGate({
  rapportId,
  langue,
  connecte,
  possede,
}: {
  rapportId: string;
  langue: Langue;
  connecte: boolean;
  possede: boolean;
}) {
  const t = traducteur(langue);
  const [ouvert, setOuvert] = useState(false);
  const [email, setEmail] = useState("");
  const [accepte, setAccepte] = useState(false);
  const [occupe, setOccupe] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [fait, setFait] = useState<{ email: string } | null>(null);

  const classeBouton =
    "flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-gold text-base font-bold text-on-gold shadow-gold-glow transition hover:brightness-110 active:scale-[0.98]";

  // Déjà à lui : on ne redemande rien.
  if (possede)
    return (
      <a href={`/beta/r/${rapportId}/pdf`} target="_blank" rel="noopener" className={classeBouton}>
        <span aria-hidden="true">⬇</span> {t("pdf_gate_title")}
      </a>
    );

  if (fait)
    return (
      <div className="rounded-xl border border-gold/40 bg-surface p-4">
        <p className="text-sm font-semibold text-ink">{t("pdf_gate_done_title")}</p>
        <p className="mt-1 text-xs text-muted">{t("pdf_gate_done_body", { email: fait.email })}</p>
        <a
          href={`/beta/r/${rapportId}/pdf`}
          target="_blank"
          rel="noopener"
          className="mt-3 inline-block rounded-md bg-gold px-4 py-2 text-sm font-semibold text-on-gold"
        >
          {t("pdf_gate_open")}
        </a>
      </div>
    );

  async function demande(e?: React.FormEvent) {
    e?.preventDefault();
    setErreur(null);
    setOccupe(true);
    const r = await fetch("/api/compte/rapport", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ rapportId, email, langue, consentement: accepte || connecte }),
    }).catch(() => null);
    setOccupe(false);
    if (!r) return setErreur(t("auth_bad"));
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg: Record<string, string> = {
        bad_email: t("auth_bad_email"),
        consent_required: t("auth_consent_required"),
        accounts_unavailable: t("auth_unavailable"),
      };
      return setErreur(msg[j.erreur] ?? t("auth_bad"));
    }
    // PAS de `router.refresh()` ici. Essayé le 2026-10-19 : le serveur renvoie
    // alors `possede = true`, le composant est remonté, et l'écran « votre mot
    // de passe part à telle adresse » disparaît avant d'avoir été lu. Le lien
    // direct revient de toute façon au prochain chargement de la page.
    setFait({ email: j.email ?? email });
  }

  // Connecté mais rapport pas encore rattaché : un seul clic, pas de formulaire.
  if (connecte && !ouvert)
    return (
      <button type="button" onClick={() => demande()} disabled={occupe} className={classeBouton}>
        <span aria-hidden="true">⬇</span> {occupe ? t("pdf_gate_working") : t("pdf_gate_title")}
      </button>
    );

  if (!ouvert)
    return (
      <button type="button" onClick={() => setOuvert(true)} className={classeBouton}>
        <span aria-hidden="true">⬇</span> {t("pdf_gate_title")}
      </button>
    );

  return (
    <form onSubmit={demande} className="rounded-xl border border-gold/40 bg-surface p-4">
      <p className="text-sm font-semibold text-ink">{t("pdf_gate_title")}</p>
      <p className="mt-1 text-xs text-muted">{t("pdf_gate_body")}</p>

      <input
        type="email"
        required
        autoFocus
        value={email}
        onChange={(ev) => setEmail(ev.target.value)}
        placeholder={t("auth_email")}
        className="mt-3 w-full rounded-md border border-rule bg-page px-3 py-2 text-ink outline-none focus:border-brand"
      />

      <label className="mt-3 flex items-start gap-2 text-xs text-muted">
        <input
          type="checkbox"
          checked={accepte}
          onChange={(ev) => setAccepte(ev.target.checked)}
          className="mt-0.5 h-4 w-4 accent-brand"
        />
        <span>
          {t("auth_consent", { privacy: "" })}{" "}
          <Link href="/beta/privacy" className="text-gold-ink underline">
            {t("auth_privacy_link")}
          </Link>
        </span>
      </label>

      {erreur && <p className="mt-2 text-sm text-red-400">{erreur}</p>}

      <button
        type="submit"
        disabled={occupe}
        className="mt-3 h-12 w-full rounded-xl bg-gold text-sm font-bold text-on-gold disabled:opacity-60"
      >
        {occupe ? t("pdf_gate_working") : t("pdf_gate_cta")}
      </button>
    </form>
  );
}

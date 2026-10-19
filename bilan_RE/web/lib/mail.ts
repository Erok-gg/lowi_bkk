/**
 * mail.ts — envoi des e-mails du bilan (mot de passe, rapport prêt).
 *
 * POURQUOI PAS DE SMTP. Il n'y a pas de SMTP sur PC2, et en ajouter un
 * signifierait stocker un mot de passe applicatif en clair sur la machine —
 * refus déjà acté pour les alertes des agents (`agents/core/alert.py`). On
 * réutilise donc EXACTEMENT le même canal : un fichier JSON déposé dans
 * `agents/queue/mail/`, que la session Claude planifiée vide par le connecteur
 * Gmail (déjà authentifié, aucun secret sur le disque).
 *
 * Conséquence à connaître : l'envoi n'est pas instantané. La page le dit
 * (« dans quelques minutes ») au lieu de laisser croire à un envoi immédiat.
 * Si un vrai SMTP arrive un jour, il se branche ici seul : `envoie()` est le
 * seul point de sortie.
 */
import "server-only";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { traceMail } from "./comptes";

export type Lettre = {
  destinataire: string;
  sujet: string;
  corps: string;
  genre: "mot_de_passe" | "rapport" | "bienvenue";
  compteId: string | null;
};

function dossierFile(): string {
  return process.env.LOWI_MAIL_DIR || path.join(process.cwd(), "agents", "queue", "mail");
}

/** Dépose la lettre dans la file et en garde la trace en base.
 *  Renvoie false si le dépôt a échoué — l'appelant doit le dire à la personne
 *  plutôt que d'afficher « e-mail envoyé » (règle 2 : pas d'alerte muette). */
export function envoie(l: Lettre): boolean {
  const horo = new Date().toISOString().replace(/[:.]/g, "").slice(0, 15);
  try {
    const dir = dossierFile();
    mkdirSync(dir, { recursive: true });
    const nom = `${horo}-bilan-${l.genre}-${Math.random().toString(36).slice(2, 8)}.json`;
    writeFileSync(
      path.join(dir, nom),
      JSON.stringify(
        { to: l.destinataire, subject: l.sujet, body: l.corps, agent: "bilan-comptes", created_at: new Date().toISOString() },
        null,
        2,
      ),
      "utf-8",
    );
    traceMail({ compteId: l.compteId, genre: l.genre, destinataire: l.destinataire, sujet: l.sujet });
    return true;
  } catch (e) {
    try {
      traceMail({
        compteId: l.compteId,
        genre: l.genre,
        destinataire: l.destinataire,
        sujet: l.sujet,
        erreur: String(e),
      });
    } catch {
      /* la base elle-même est indisponible : rien de plus à faire ici */
    }
    return false;
  }
}

/* ────────────────────────────── les deux lettres ─────────────────────────── */

/* Les lettres suivent la langue CHOISIE par la personne (en / th / zh). Elles
 * ne passent pas par le dictionnaire de l'interface : un e-mail a ses propres
 * tournures, et mélanger les deux ferait des phrases d'interface dans un
 * courrier. Traductions de travail, à faire relire comme le reste. */

const LETTRES = {
  mot_de_passe: {
    en: {
      sujet: "Your Lowi access",
      corps: (email: string, mdp: string, lien: string) =>
        `Hello,\n\nYour Lowi account is ready.\n\nLogin: ${email}\nPassword: ${mdp}\n\nSign in: ${lien}\nYou can change this password once signed in.\n\n— Lowi`,
    },
    th: {
      sujet: "ข้อมูลการเข้าใช้งาน Lowi ของคุณ",
      corps: (email: string, mdp: string, lien: string) =>
        `สวัสดีครับ/ค่ะ\n\nบัญชี Lowi ของคุณพร้อมใช้งานแล้ว\n\nชื่อผู้ใช้: ${email}\nรหัสผ่าน: ${mdp}\n\nเข้าสู่ระบบ: ${lien}\nคุณเปลี่ยนรหัสผ่านได้หลังเข้าสู่ระบบ\n\n— Lowi`,
    },
    zh: {
      sujet: "您的 Lowi 账户信息",
      corps: (email: string, mdp: string, lien: string) =>
        `您好，\n\n您的 Lowi 账户已创建。\n\n登录名：${email}\n密码：${mdp}\n\n登录地址：${lien}\n登录后可自行修改密码。\n\n— Lowi`,
    },
  },
  rapport: {
    en: {
      sujet: "Your Lowi report is ready",
      corps: (lien: string) =>
        `Hello,\n\nYour report is ready: ${lien}\nIt stays in your account — reopen or download it any time.\n\n— Lowi`,
    },
    th: {
      sujet: "รายงาน Lowi ของคุณพร้อมแล้ว",
      corps: (lien: string) =>
        `สวัสดีครับ/ค่ะ\n\nรายงานของคุณพร้อมแล้ว: ${lien}\nรายงานจะอยู่ในบัญชีของคุณ เปิดหรือดาวน์โหลดได้ทุกเมื่อ\n\n— Lowi`,
    },
    zh: {
      sujet: "您的 Lowi 报告已就绪",
      corps: (lien: string) =>
        `您好，\n\n您的报告已就绪：${lien}\n报告保存在您的账户中，可随时打开或下载。\n\n— Lowi`,
    },
  },
} as const;

type Code = keyof (typeof LETTRES)["rapport"];
const code = (langue: string): Code => (langue === "th" || langue === "zh" ? langue : "en");

export function lettreMotDePasse(email: string, motDePasse: string, lien: string, langue: string): Lettre {
  const l = LETTRES.mot_de_passe[code(langue)];
  return {
    destinataire: email,
    compteId: null,
    genre: "mot_de_passe",
    sujet: l.sujet,
    corps: l.corps(email, motDePasse, lien),
  };
}

export function lettreRapport(email: string, lien: string, langue: string, compteId: string): Lettre {
  const l = LETTRES.rapport[code(langue)];
  return { destinataire: email, compteId, genre: "rapport", sujet: l.sujet, corps: l.corps(lien) };
}

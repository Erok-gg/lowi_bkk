import { i18n } from "@/bilan_RE/web/lib/langue";
import { VERSION_CONSENTEMENT } from "@/bilan_RE/web/lib/consentement-version";
import type { Langue } from "@/bilan_RE/web/i18n";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Notice de confidentialité — ce que le bandeau et les formulaires pointent.
 *
 * ⚠ TEXTE DE TRAVAIL, pas un document validé. Il dit la vérité de ce que le
 * code fait aujourd'hui (c'est déjà plus que rien, et vérifiable ligne à
 * ligne), mais il n'a PAS été relu par un juriste. Deux points doivent l'être
 * avant toute ouverture au public : le régime applicable (PDPA thaïlandaise si
 * la société est thaïe, RGPD si des résidents de l'UE sont visés — les deux en
 * pratique), et l'identité du responsable du traitement, qui dépend de la forme
 * sociale encore à trancher (backlog §4, journal-juridique).
 * Les traductions thaï et chinoise sont de travail elles aussi.
 */

type Bloc = { titre: string; corps: string[] };

const TEXTES: Record<Langue, { titre: string; maj: string; blocs: Bloc[] }> = {
  en: {
    titre: "Privacy notice",
    maj: "Version",
    blocs: [
      {
        titre: "What we collect",
        corps: [
          "Your email address, when you ask for a report or create an account. That is the only thing we ask for at sign-up.",
          "If you buy a report later, we will also ask for your name, first name, date of birth and nationality. Those fields stay empty until then.",
          "The reports you requested, so you can reopen them.",
          "Your cookie choice, with the version of this notice you were shown.",
        ],
      },
      {
        titre: "What we do with it",
        corps: [
          "Send you your password and your reports, and let you sign back in.",
          "Keep your reports available in your account.",
          "Nothing else. We do not sell or share this data, and we send no marketing email unless you ask for it.",
        ],
      },
      {
        titre: "Cookies",
        corps: [
          "Necessary: signing you in (session cookie), your language, your cookie choice. These cannot be switched off — without them the site cannot keep you signed in.",
          "Measurement and marketing: optional, off unless you turn them on. As of this version, no such script is loaded at all.",
        ],
      },
      {
        titre: "Where it is stored, and for how long",
        corps: [
          "On our own machine, in a database separate from the market data. Listing data and personal data are never mixed.",
          "Your account stays until you ask us to delete it. Ask at the address below and the personal fields are erased.",
        ],
      },
      {
        titre: "Your rights",
        corps: [
          "You can ask for a copy of your data, a correction, or its deletion, by email.",
          "Write to: schoenauer.anthony@gmail.com",
        ],
      },
      {
        titre: "About the reports themselves",
        corps: [
          "A report is a market analysis built from public listings: asking prices and listing exits, not confirmed sale prices. It is not a valuation by a licensed appraiser, and it is not investment advice.",
        ],
      },
    ],
  },
  th: {
    titre: "ประกาศความเป็นส่วนตัว",
    maj: "เวอร์ชัน",
    blocs: [
      {
        titre: "ข้อมูลที่เราเก็บ",
        corps: [
          "อีเมลของคุณ เมื่อคุณขอรายงานหรือสร้างบัญชี ตอนสมัครเราขอเพียงเท่านี้",
          "หากคุณซื้อรายงานในภายหลัง เราจะขอชื่อ นามสกุล วันเกิด และสัญชาติ ช่องเหล่านี้ว่างไว้จนถึงตอนนั้น",
          "รายงานที่คุณขอ เพื่อให้คุณเปิดดูซ้ำได้",
          "ตัวเลือกคุกกี้ของคุณ พร้อมเวอร์ชันของประกาศฉบับที่คุณเห็น",
        ],
      },
      {
        titre: "เราใช้ทำอะไร",
        corps: [
          "ส่งรหัสผ่านและรายงานให้คุณ และให้คุณกลับเข้าสู่ระบบได้",
          "เก็บรายงานไว้ในบัญชีของคุณ",
          "ไม่มีอย่างอื่น เราไม่ขายและไม่แบ่งปันข้อมูลนี้ และไม่ส่งอีเมลการตลาดเว้นแต่คุณขอ",
        ],
      },
      {
        titre: "คุกกี้",
        corps: [
          "ที่จำเป็น: การเข้าสู่ระบบ ภาษา และตัวเลือกคุกกี้ ปิดไม่ได้ เพราะหากไม่มี ระบบจะจำการเข้าสู่ระบบไม่ได้",
          "การวัดผลและการตลาด: เป็นทางเลือก ปิดอยู่จนคุณเปิด ในเวอร์ชันนี้ยังไม่มีสคริปต์ประเภทนี้เลย",
        ],
      },
      {
        titre: "เก็บที่ไหน นานเท่าไร",
        corps: [
          "บนเครื่องของเราเอง ในฐานข้อมูลที่แยกจากข้อมูลตลาด ข้อมูลประกาศและข้อมูลส่วนบุคคลไม่ถูกรวมกัน",
          "บัญชีของคุณคงอยู่จนคุณขอให้ลบ แจ้งที่อีเมลด้านล่าง แล้วข้อมูลส่วนบุคคลจะถูกลบ",
        ],
      },
      {
        titre: "สิทธิของคุณ",
        corps: [
          "คุณขอสำเนาข้อมูล ขอแก้ไข หรือขอลบได้ทางอีเมล",
          "ติดต่อ: schoenauer.anthony@gmail.com",
        ],
      },
      {
        titre: "เกี่ยวกับรายงาน",
        corps: [
          "รายงานเป็นการวิเคราะห์ตลาดจากประกาศสาธารณะ ใช้ราคาเสนอขายและการถอนประกาศ ไม่ใช่ราคาซื้อขายจริง ไม่ใช่การประเมินราคาโดยผู้ประเมินที่ได้รับอนุญาต และไม่ใช่คำแนะนำการลงทุน",
        ],
      },
    ],
  },
  zh: {
    titre: "隐私声明",
    maj: "版本",
    blocs: [
      {
        titre: "我们收集什么",
        corps: [
          "您索取报告或创建账户时提供的邮箱地址。注册时我们只要这一项。",
          "若日后购买报告，我们还会索取姓名、名字、出生日期与国籍。在那之前这些字段为空。",
          "您索取过的报告，便于您再次打开。",
          "您的 cookie 选择，以及当时向您展示的本声明版本。",
        ],
      },
      {
        titre: "我们如何使用",
        corps: [
          "向您发送密码与报告，并让您重新登录。",
          "把报告保存在您的账户中。",
          "仅此而已。我们不出售、不共享这些数据，未经您要求也不发送营销邮件。",
        ],
      },
      {
        titre: "Cookie",
        corps: [
          "必需：登录（会话 cookie）、语言、cookie 选择。无法关闭，否则网站无法维持登录状态。",
          "统计与营销：可选，未经开启即关闭。在本版本中，完全没有加载此类脚本。",
        ],
      },
      {
        titre: "存放地点与期限",
        corps: [
          "存放在我们自己的机器上，与市场数据分属不同数据库。房源数据与个人数据从不混合。",
          "您的账户一直保留，直到您要求删除。写邮件到下列地址，个人字段将被清除。",
        ],
      },
      {
        titre: "您的权利",
        corps: ["您可以通过邮件索取数据副本、要求更正或删除。", "联系：schoenauer.anthony@gmail.com"],
      },
      {
        titre: "关于报告本身",
        corps: [
          "报告是基于公开房源的市场分析，使用挂牌价与下架记录，而非确认成交价。它不是持牌估价师出具的估价，也不构成投资建议。",
        ],
      },
    ],
  },
};

export default async function Privacy() {
  const { langue } = await i18n();
  const txt = TEXTES[langue] ?? TEXTES.en;
  return (
    <div className="h-full overflow-y-auto">
      <article className="mx-auto max-w-2xl px-4 pb-20 pt-10">
        <h1 className="text-2xl font-semibold text-text">{txt.titre}</h1>
        <p className="mt-1 text-xs text-text-faint">
          {txt.maj} {VERSION_CONSENTEMENT}
        </p>
        {txt.blocs.map((b) => (
          <section key={b.titre} className="mt-7">
            <h2 className="text-base font-semibold text-text">{b.titre}</h2>
            <ul className="mt-2 space-y-2">
              {b.corps.map((p) => (
                <li key={p} className="text-sm leading-relaxed text-text-muted">
                  {p}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </article>
    </div>
  );
}

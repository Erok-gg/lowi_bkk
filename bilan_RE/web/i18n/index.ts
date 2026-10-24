/**
 * i18n — trois langues au départ : anglais, thaï, chinois (demande du 2026-10-19).
 *
 * Pas de bibliothèque : un objet par langue, l'anglais sert de référence de
 * typage (une clé oubliée ailleurs est une erreur de compilation, pas un trou
 * silencieux dans la page). Le reste du site privé (carte, tableaux) reste en
 * anglais seul — c'est l'outil interne, pas le produit.
 *
 * ⚠ Les textes thaïs et chinois sont des traductions de travail, non relues par
 * un locuteur natif. À faire relire avant d'ouvrir au public : une faute de ton
 * sur une page qui parle d'argent coûte la confiance.
 */

export const LANGUES = ["en", "th", "zh"] as const;
export type Langue = (typeof LANGUES)[number];
export const LANGUE_DEFAUT: Langue = "en";

export const NOMS: Record<Langue, string> = {
  en: "English",
  th: "ไทย",
  zh: "中文",
};

const en = {
  /* nav publique */
  nav_signin: "Sign in",
  nav_signup: "Sign up",
  nav_reports: "My reports",
  nav_signout: "Sign out",
  nav_language: "Language",

  /* landing */
  land_badge: "Private beta",
  land_title_a: "Independent insight.",
  land_title_em: "",
  land_title_b: "Better property decisions.",
  land_sub: "Lowi is an independent real estate market analysis service that evaluates property opportunities using structured market data, proprietary analytics and independent comparisons.",
  land_free: "Free summary · full report as PDF · Lowi takes nothing from the seller",
  land_disclaimer:
    "Based on asking prices and listing exits, not confirmed sales. Market analysis, not a valuation, and not investment advice.",
  land_p1_t: "Is the price right?",
  land_p1_d: "Price per m² against the same building, the same beds and size, within 1 km.",
  land_p2_t: "Is the seller in a hurry?",
  land_p2_d: "How long it has been listed, on how many portals, and every price cut.",
  land_p3_t: "Who has the upper hand?",
  land_p3_d: "A buyer's-or-seller's market score out of 100, with the sample behind it.",
  land_p4_t: "Will it resell?",
  land_p4_d: "How fast similar units sell at market price, and how that changes as the building ages.",

  /* champ d'analyse de la landing */
  form_label: "Link of the listing",
  form_cta: "Analyse this listing",
  form_need_link: "Paste the link of a listing first.",
  form_failed: "Something went wrong. Try again.",

  /* comptes */
  auth_signin_title: "Sign in",
  auth_signup_title: "Create your account",
  auth_email: "Email",
  auth_password: "Password",
  auth_signup_only_email: "We only ask for your email. Nothing else, for now.",
  auth_signup_cta: "Create my account",
  auth_signin_cta: "Sign in",
  auth_have_account: "Already have an account?",
  auth_no_account: "No account yet?",
  auth_sent_title: "Check your inbox",
  auth_sent_body: "We are sending your password to {email}. It can take a few minutes to arrive.",
  auth_forgot: "Forgot your password?",
  auth_forgot_sent: "If that address has an account, a new password is on its way.",
  auth_bad: "Wrong email or password.",
  auth_bad_email: "This does not look like an email address.",
  auth_consent_required: "Please accept the privacy notice to continue.",
  auth_consent: "I have read the {privacy}.",
  auth_privacy_link: "privacy notice",
  auth_unavailable: "Accounts are not available on this server.",

  /* mes rapports */
  rep_title: "My reports",
  rep_empty: "No report yet. Paste a listing link to get your first one.",
  rep_open: "Open",
  rep_pdf: "PDF",
  rep_paid: "Full report",
  rep_free: "Free summary",
  rep_analyse_another: "Analyse another listing",

  /* porte du PDF */
  pdf_gate_title: "Save the report as PDF",
  pdf_gate_body:
    "We send it to your email and keep it in your account, so you can reopen or download it later.",
  pdf_gate_cta: "Send me the report",
  pdf_gate_working: "Preparing…",
  pdf_gate_done_title: "On its way",
  pdf_gate_done_body: "The report is in your account. Your password is being emailed to {email}.",
  pdf_gate_open: "Open the report now",

  /* cookies / données */
  cookie_title: "Cookies and your data",
  cookie_body:
    "We use cookies that are needed to sign you in and keep your reports. Anything else is optional and off until you say yes.",
  cookie_accept: "Accept all",
  cookie_refuse: "Necessary only",
  cookie_choose: "Choose",
  cookie_save: "Save my choice",
  cookie_necessary: "Necessary",
  cookie_necessary_d: "Sign-in and your saved reports. Cannot be switched off.",
  cookie_measure: "Measurement",
  cookie_measure_d: "Counting how pages are used, to improve them.",
  cookie_marketing: "Marketing",
  cookie_marketing_d: "Nothing today. Off unless you turn it on.",
  cookie_more: "Privacy notice",
} as const;

export type Cles = keyof typeof en;

const th: Record<Cles, string> = {
  nav_signin: "เข้าสู่ระบบ",
  nav_signup: "สมัคร",
  nav_reports: "รายงานของฉัน",
  nav_signout: "ออกจากระบบ",
  nav_language: "ภาษา",

  land_badge: "รุ่นทดลอง",
  land_title_a: "ข้อมูลเชิงลึกที่เป็นอิสระ",
  land_title_em: "",
  land_title_b: "การตัดสินใจเรื่องอสังหาริมทรัพย์ที่ดีกว่า",
  land_sub: "Lowi เป็นบริการวิเคราะห์ตลาดอสังหาริมทรัพย์อิสระ ประเมินโอกาสด้านอสังหาริมทรัพย์ด้วยข้อมูลตลาดที่เป็นระบบ การวิเคราะห์เฉพาะของเรา และการเปรียบเทียบที่เป็นอิสระ",
  land_free: "สรุปฟรี · รายงานเต็มเป็น PDF · Lowi ไม่รับเงินจากผู้ขาย",
  land_disclaimer:
    "คำนวณจากราคาเสนอขายและการถอนประกาศ ไม่ใช่ราคาซื้อขายจริง เป็นการวิเคราะห์ตลาด ไม่ใช่การประเมินราคาและไม่ใช่คำแนะนำการลงทุน",
  land_p1_t: "ราคานี้สมเหตุสมผลไหม",
  land_p1_d: "ราคาต่อตารางเมตรเทียบกับตึกเดียวกัน จำนวนห้องนอนและขนาดเท่ากัน ในรัศมี 1 กม.",
  land_p2_t: "ผู้ขายรีบขายหรือไม่",
  land_p2_d: "ประกาศมานานเท่าไร อยู่บนกี่เว็บไซต์ และลดราคามากี่ครั้ง",
  land_p3_t: "ใครมีอำนาจต่อรอง",
  land_p3_d: "คะแนนตลาดผู้ซื้อหรือผู้ขายเต็ม 100 พร้อมจำนวนตัวอย่างที่ใช้",
  land_p4_t: "ขายต่อได้ไหม",
  land_p4_d: "ห้องแบบเดียวกันขายได้เร็วแค่ไหนที่ราคาตลาด และเปลี่ยนไปอย่างไรเมื่อตึกเก่าลง",

  form_label: "ลิงก์ประกาศ",
  form_cta: "วิเคราะห์ประกาศนี้",
  form_need_link: "กรุณาวางลิงก์ประกาศก่อน",
  form_failed: "เกิดข้อผิดพลาด กรุณาลองใหม่",

  auth_signin_title: "เข้าสู่ระบบ",
  auth_signup_title: "สร้างบัญชี",
  auth_email: "อีเมล",
  auth_password: "รหัสผ่าน",
  auth_signup_only_email: "เราขอเพียงอีเมลของคุณเท่านั้น",
  auth_signup_cta: "สร้างบัญชีของฉัน",
  auth_signin_cta: "เข้าสู่ระบบ",
  auth_have_account: "มีบัญชีอยู่แล้ว?",
  auth_no_account: "ยังไม่มีบัญชี?",
  auth_sent_title: "ตรวจอีเมลของคุณ",
  auth_sent_body: "เรากำลังส่งรหัสผ่านไปที่ {email} อาจใช้เวลาสองสามนาที",
  auth_forgot: "ลืมรหัสผ่าน?",
  auth_forgot_sent: "หากอีเมลนี้มีบัญชีอยู่ รหัสผ่านใหม่กำลังถูกส่งไป",
  auth_bad: "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
  auth_bad_email: "รูปแบบอีเมลไม่ถูกต้อง",
  auth_consent_required: "กรุณายอมรับประกาศความเป็นส่วนตัวก่อนดำเนินการต่อ",
  auth_consent: "ฉันได้อ่าน{privacy}แล้ว",
  auth_privacy_link: "ประกาศความเป็นส่วนตัว",
  auth_unavailable: "เซิร์ฟเวอร์นี้ยังไม่เปิดให้สร้างบัญชี",

  rep_title: "รายงานของฉัน",
  rep_empty: "ยังไม่มีรายงาน วางลิงก์ประกาศเพื่อเริ่มฉบับแรก",
  rep_open: "เปิด",
  rep_pdf: "PDF",
  rep_paid: "รายงานเต็ม",
  rep_free: "สรุปฟรี",
  rep_analyse_another: "วิเคราะห์ประกาศอื่น",

  pdf_gate_title: "รับรายงานฉบับเต็มเป็น PDF",
  pdf_gate_body: "เราส่งไปที่อีเมลของคุณและเก็บไว้ในบัญชี เปิดหรือดาวน์โหลดภายหลังได้",
  pdf_gate_cta: "ส่งรายงานให้ฉัน",
  pdf_gate_working: "กำลังเตรียม…",
  pdf_gate_done_title: "กำลังส่ง",
  pdf_gate_done_body: "รายงานอยู่ในบัญชีของคุณแล้ว รหัสผ่านกำลังถูกส่งไปที่ {email}",
  pdf_gate_open: "เปิดรายงานเลย",

  cookie_title: "คุกกี้และข้อมูลของคุณ",
  cookie_body:
    "เราใช้คุกกี้ที่จำเป็นสำหรับการเข้าสู่ระบบและเก็บรายงานของคุณ ส่วนอื่นเป็นทางเลือกและปิดอยู่จนคุณอนุญาต",
  cookie_accept: "ยอมรับทั้งหมด",
  cookie_refuse: "เฉพาะที่จำเป็น",
  cookie_choose: "เลือกเอง",
  cookie_save: "บันทึกการเลือก",
  cookie_necessary: "จำเป็น",
  cookie_necessary_d: "การเข้าสู่ระบบและรายงานที่บันทึกไว้ ปิดไม่ได้",
  cookie_measure: "การวัดผล",
  cookie_measure_d: "นับการใช้งานหน้าเว็บเพื่อปรับปรุง",
  cookie_marketing: "การตลาด",
  cookie_marketing_d: "ยังไม่มีการใช้ ปิดอยู่จนคุณเปิด",
  cookie_more: "ประกาศความเป็นส่วนตัว",
};

const zh: Record<Cles, string> = {
  nav_signin: "登录",
  nav_signup: "注册",
  nav_reports: "我的报告",
  nav_signout: "退出",
  nav_language: "语言",

  land_badge: "内测版",
  land_title_a: "独立洞察，",
  land_title_em: "",
  land_title_b: "",
  land_sub: "Lowi 是一项独立的房地产市场分析服务，基于结构化市场数据、自有分析模型和独立对比来评估房产机会。",
  land_free: "免费摘要 · 完整报告为 PDF · Lowi 不收卖方一分钱",
  land_disclaimer: "基于挂牌价与下架记录，而非成交价。这是市场分析，不是估价，也不构成投资建议。",
  land_p1_t: "价格合理吗？",
  land_p1_d: "与同一栋楼、同样房型与面积、1 公里内的每平米价格对比。",
  land_p2_t: "卖方着急吗？",
  land_p2_d: "挂牌多久、在几个网站上挂、降过几次价。",
  land_p3_t: "谈判的主动权在谁手里？",
  land_p3_d: "买方／卖方市场评分（满分 100），并附样本数量。",
  land_p4_t: "好转手吗？",
  land_p4_d: "同类单位按市价卖出的速度，以及楼龄增长后的变化。",

  form_label: "房源链接",
  form_cta: "分析这个房源",
  form_need_link: "请先粘贴房源链接。",
  form_failed: "出错了，请重试。",

  auth_signin_title: "登录",
  auth_signup_title: "创建账户",
  auth_email: "邮箱",
  auth_password: "密码",
  auth_signup_only_email: "我们只需要您的邮箱，暂不索取其他信息。",
  auth_signup_cta: "创建账户",
  auth_signin_cta: "登录",
  auth_have_account: "已有账户？",
  auth_no_account: "还没有账户？",
  auth_sent_title: "请查看邮箱",
  auth_sent_body: "密码正在发送至 {email}，可能需要几分钟。",
  auth_forgot: "忘记密码？",
  auth_forgot_sent: "如果该邮箱已注册，新密码正在发送中。",
  auth_bad: "邮箱或密码不正确。",
  auth_bad_email: "这看起来不是一个邮箱地址。",
  auth_consent_required: "请先接受隐私声明。",
  auth_consent: "我已阅读{privacy}。",
  auth_privacy_link: "隐私声明",
  auth_unavailable: "此服务器暂不支持账户功能。",

  rep_title: "我的报告",
  rep_empty: "还没有报告。粘贴一个房源链接即可生成第一份。",
  rep_open: "打开",
  rep_pdf: "PDF",
  rep_paid: "完整报告",
  rep_free: "免费摘要",
  rep_analyse_another: "分析另一个房源",

  pdf_gate_title: "获取完整 PDF 报告",
  pdf_gate_body: "我们会发送到您的邮箱，并保存在账户中，便于日后查看或下载。",
  pdf_gate_cta: "把报告发给我",
  pdf_gate_working: "正在准备…",
  pdf_gate_done_title: "正在发送",
  pdf_gate_done_body: "报告已存入您的账户，密码正在发送至 {email}。",
  pdf_gate_open: "立即打开报告",

  cookie_title: "Cookie 与您的数据",
  cookie_body: "我们使用登录和保存报告所必需的 cookie。其他用途均为可选，未经同意不会启用。",
  cookie_accept: "全部接受",
  cookie_refuse: "仅必需",
  cookie_choose: "自行选择",
  cookie_save: "保存选择",
  cookie_necessary: "必需",
  cookie_necessary_d: "登录与已保存的报告，无法关闭。",
  cookie_measure: "统计",
  cookie_measure_d: "统计页面使用情况以便改进。",
  cookie_marketing: "营销",
  cookie_marketing_d: "目前没有使用，除非您开启。",
  cookie_more: "隐私声明",
};

export const DICTS: Record<Langue, Record<Cles, string>> = { en, th, zh };

/** Traduit, et remplace les {jetons} par les valeurs données.
 *  Une clé absente retombe sur l'anglais : une page incomplète reste lisible. */
export function traduis(langue: Langue, cle: Cles, vars?: Record<string, string>): string {
  const brut = DICTS[langue]?.[cle] ?? en[cle];
  if (!vars) return brut;
  return brut.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);
}

export type T = (cle: Cles, vars?: Record<string, string>) => string;

export function traducteur(langue: Langue): T {
  return (cle, vars) => traduis(langue, cle, vars);
}

export function langueValide(v: string | undefined | null): Langue {
  return (LANGUES as readonly string[]).includes(v ?? "") ? (v as Langue) : LANGUE_DEFAUT;
}

/** Première langue connue dans un en-tête Accept-Language. `zh-TW`, `th-TH` →
 *  `zh`, `th`. On ne gère pas encore le traditionnel séparément. */
export function langueDepuisEntete(entete: string | null | undefined): Langue | null {
  if (!entete) return null;
  for (const morceau of entete.split(",")) {
    const code = morceau.split(";")[0].trim().toLowerCase().split("-")[0];
    if ((LANGUES as readonly string[]).includes(code)) return code as Langue;
  }
  return null;
}

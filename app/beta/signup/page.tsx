import { redirect } from "next/navigation";
import AuthForm from "@/bilan_RE/web/components/AuthForm";
import { i18n } from "@/bilan_RE/web/lib/langue";
import { compteCourant } from "@/bilan_RE/web/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function Inscription() {
  if (await compteCourant()) redirect("/beta/reports");
  const { langue } = await i18n();
  return (
    <div className="flex h-full items-center justify-center overflow-y-auto px-4 py-10">
      <AuthForm langue={langue} mode="signup" />
    </div>
  );
}

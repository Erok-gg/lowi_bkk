import type { Metadata } from "next";
import "./globals.css";
import LowiHeader from "@/components/LowiHeader";
import { SearchProvider } from "@/components/SearchProvider";
import CookieBanner from "@/bilan_RE/web/components/CookieBanner";
import { langueCourante } from "@/bilan_RE/web/lib/langue";
import { compteCourant } from "@/bilan_RE/web/lib/session";

export const metadata: Metadata = {
  title: "Lowi BKK — Real estate map",
  description: "Interactive Bangkok real estate map (private)",
  robots: "noindex, nofollow",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Langue et compte sont résolus ICI, une fois, et descendus en props : le
  // header et le bandeau sont des composants navigateur et ne peuvent pas lire
  // les cookies eux-mêmes. `compteCourant()` ne coûte rien quand les comptes
  // sont désactivés (Vercel) : il sort sur une variable d'environnement.
  const [langue, compte] = await Promise.all([langueCourante(), compteCourant()]);

  return (
    <html lang={langue}>
      <body className="bg-anthracite-deep text-text antialiased">
        <SearchProvider>
          <div className="flex h-screen flex-col overflow-hidden print:block print:h-auto print:overflow-visible">
            <LowiHeader langue={langue} email={compte?.email_saisi ?? compte?.email ?? null} />
            <main className="relative min-h-0 flex-1 print:overflow-visible">{children}</main>
          </div>
          <CookieBanner langue={langue} />
        </SearchProvider>
      </body>
    </html>
  );
}

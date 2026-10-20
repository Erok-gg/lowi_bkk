import type { Metadata } from "next";
import { Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import LowiHeader from "@/components/LowiHeader";
import { SearchProvider } from "@/components/SearchProvider";
import CookieBanner from "@/bilan_RE/web/components/CookieBanner";
import { langueCourante } from "@/bilan_RE/web/lib/langue";
import { compteCourant } from "@/bilan_RE/web/lib/session";
import { cssTokens } from "@/config/theme";

/**
 * Les deux polices du systeme de design du pitch (`lowi-th/Design-ledger.md`,
 * principe 1 : une police de texte, une police de donnees). AUTO-HEBERGEES par
 * next/font, pas un `<link>` vers Google : le Ledger a ete ecrit apres avoir
 * mesure qu'`Aptos` n'existait que sur le poste de test, et qu'un visiteur sur
 * Mac lisait une autre police que celle validee a l'ecran.
 *
 * Declarees ici pour que le header (hors du layout `/beta`) en dispose aussi.
 * Elles ne sont TELECHARGEES que si une regle rendue les utilise : seul le
 * sous-arbre `.theme-ledger` reference `var(--police-texte)`, donc la carte et
 * les tableaux ne paient rien. MCTen reste sur le seul logo, c'est la marque.
 */
const policeTexte = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--police-texte",
  display: "swap",
});

const policeDonnees = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--police-donnees",
  display: "swap",
});

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
      <head>
        {/* Jetons de couleur : `:root` = theme sombre (carte, tableaux),
            `.theme-ledger` = vert/or/blanc (pages du bilan acheteur). Generes
            depuis config/theme.ts pour n'avoir qu'une seule source. */}
        <style dangerouslySetInnerHTML={{ __html: cssTokens() }} />
      </head>
      <body className={`${policeTexte.variable} ${policeDonnees.variable} bg-anthracite-deep text-text antialiased`}>
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

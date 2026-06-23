import type { Metadata } from "next";
import "./globals.css";
import LowiHeader from "@/components/LowiHeader";

export const metadata: Metadata = {
  title: "Lowi BKK — Real estate map",
  description: "Interactive Bangkok real estate map (private)",
  robots: "noindex, nofollow",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-anthracite-deep text-text antialiased">
        <div className="flex h-screen flex-col overflow-hidden">
          <LowiHeader />
          <main className="relative min-h-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}

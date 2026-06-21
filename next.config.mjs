import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const projectRoot = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // false : évite le double-mount dev qui annule le chargement du style MapLibre
  reactStrictMode: false,
  // Évite que Next remonte au lockfile du dossier utilisateur
  outputFileTracingRoot: projectRoot,
  images: {
    // Supabase Storage public bucket pour les images de biens (webp)
    remotePatterns: [
      { protocol: "https", hostname: "*.supabase.co" },
    ],
  },
};

export default nextConfig;

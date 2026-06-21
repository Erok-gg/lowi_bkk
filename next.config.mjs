/** @type {import('next').NextConfig} */
const nextConfig = {
  // false : évite le double-mount dev qui annule le chargement du style MapLibre
  reactStrictMode: false,
  images: {
    // Supabase Storage public bucket pour les images de biens (webp)
    remotePatterns: [{ protocol: "https", hostname: "*.supabase.co" }],
  },
};

export default nextConfig;

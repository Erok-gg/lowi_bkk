/**
 * image-url.ts — Résout l'URL d'affichage d'une image de bien.
 * - Si NEXT_PUBLIC_SUPABASE_URL est défini → URL publique Supabase Storage
 *   (bucket "listings", chemin = storage_path) → marche sur Vercel.
 * - Sinon → route locale /api/img (lecture de scraper/output) pour le dev.
 */
const BUCKET = "listings";

export function imageUrl(storagePath: string): string {
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (base) {
    return `${base}/storage/v1/object/public/${BUCKET}/${storagePath}`;
  }
  return `/api/img?p=${encodeURIComponent(storagePath)}`;
}

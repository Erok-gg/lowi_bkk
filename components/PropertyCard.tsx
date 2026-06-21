"use client";

import type { Listing } from "@/lib/types";
import { PROPERTY_CARD_SECTIONS } from "@/config/property-card.config";
import { imageUrl } from "@/lib/image-url";

/**
 * PropertyCard — fiche bien DATA-DRIVEN (config/property-card.config.ts).
 * 3 sections : résumé · amenities · proximité. Aucune logique de présentation
 * en dur : on itère sur la config.
 */
export default function PropertyCard({ listing }: { listing: Listing }) {
  const img = listing.images?.[0];
  const imgUrl = img ? imageUrl(img.storagePath) : null;

  return (
    <div className="w-80 overflow-hidden rounded-lg border border-violet-soft bg-surface shadow-xl">
      {imgUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={imgUrl} alt={listing.title} className="h-40 w-full object-cover" />
      )}
      <div className="max-h-[60vh] overflow-y-auto p-3">
        {PROPERTY_CARD_SECTIONS.filter((s) => s.enabled !== false).map((section) => {
          if (section.kind === "list") {
            const items = section.getList?.(listing) ?? [];
            if (items.length === 0) return null;
            return (
              <section key={section.id} className="mb-3">
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gold">
                  {section.title}
                </h3>
                <div className="flex flex-wrap gap-1">
                  {items.map((it) => (
                    <span key={it} className="rounded bg-anthracite-deep px-1.5 py-0.5 text-[11px] text-text-muted">
                      {it}
                    </span>
                  ))}
                </div>
              </section>
            );
          }
          const fields = (section.fields ?? [])
            .filter((f) => f.enabled !== false)
            .map((f) => ({ label: f.label, value: f.get(listing) }))
            .filter((f) => f.value != null);
          if (fields.length === 0) return null;
          return (
            <section key={section.id} className="mb-3">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gold">
                {section.title}
              </h3>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                {fields.map((f) => (
                  <div key={f.label} className="contents">
                    <dt className="text-text-faint">{f.label}</dt>
                    <dd className="text-right text-text">{f.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          );
        })}
        <a href={listing.sourceUrl} target="_blank" rel="noreferrer"
           className="mt-1 block text-center text-[11px] text-violet-fluo hover:underline">
          Voir l&apos;annonce ({listing.source}) ↗
        </a>
      </div>
    </div>
  );
}

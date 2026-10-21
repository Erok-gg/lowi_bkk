/**
 * Nom affiché de chaque source. L'identifiant (`fazwaz`, `ddproperty`…) reste
 * celui de la base : il préfixe les ~86 000 identifiants d'annonce FazWaz et
 * l'historique des agents — le renommer casserait ces liens.
 *
 * « FazWaz / Thaiger » (2026-10-21) : thaigerproperty.com est une vitrine du
 * groupe FazWaz, même catalogue (58 annonces sur 60 testées déjà en base, mêmes
 * totaux Bangkok). Une seule source, deux portails.
 */
export const SOURCE_LABELS: Record<string, string> = {
  fazwaz: "FazWaz / Thaiger",
  ddproperty: "DDproperty",
  propertyscout: "PropertyScout",
  nestopa: "Nestopa",
  livinginsider: "LivingInsider",
  propertyhub: "PropertyHub",
  hipflat: "Hipflat",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

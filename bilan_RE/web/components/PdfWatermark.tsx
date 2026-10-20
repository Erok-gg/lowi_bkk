/**
 * Filigrane des rapports imprimés — le logo en grand à 45°, « beta » dessous.
 *
 * UNE SEULE opacité, portée par le conteneur : le logo et la mention ont donc
 * exactement le même alpha, quoi qu'on change ensuite de leurs tailles
 * respectives (demande du 2026-10-20). Même police que le logo (MCTen) pour
 * les deux.
 *
 * `position:fixed` (dans `globals.css`) est ce qui le fait réapparaître sur
 * CHAQUE page du PDF : un élément en flux ne serait imprimé qu'une fois.
 * Il est posé À L'INTÉRIEUR de la feuille blanche, sinon le fond opaque de
 * celle-ci le recouvrirait ; le contenu du rapport repasse au-dessus avec son
 * propre `z-index`.
 */
export default function PdfWatermark() {
  return (
    <div className="pdf-filigrane" aria-hidden="true">
      <div className="pdf-filigrane__bloc">
        <span className="pdf-filigrane__mot font-logo">lowi</span>
        <span className="pdf-filigrane__beta font-logo">beta</span>
      </div>
    </div>
  );
}

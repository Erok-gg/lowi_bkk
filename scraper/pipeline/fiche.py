"""fiche.py — Génère une fiche HTML autonome par annonce (thème dark).

Sections : (1) le bien, (2) amenities, (3) proximité (placeholder tant que la
proximité n'est pas calculée). Écrit dans output/fiches/<id>.html.
"""
from __future__ import annotations

import html
from pathlib import Path


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else "—"


def _fmt_price(p, cur) -> str:
    return f"{int(p):,} {cur}".replace(",", " ") if p else "—"


def write_fiche(norm: dict, images: list[dict], out_root: Path) -> Path:
    safe = norm["id"].replace(":", "_").replace("/", "_")
    out_dir = out_root / "fiches"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe}.html"

    img_tag = ""
    if images:
        # chemin relatif depuis fiches/ vers images/
        rel = "../" + images[0]["storage_path"]
        img_tag = f'<img src="{_esc(rel)}" alt="{_esc(norm.get("title"))}" />'

    ppsqm = norm.get("price_per_sqm")
    rows = [
        ("Nom", norm.get("condo_name") or norm.get("title")),
        ("Prix", _fmt_price(norm.get("price"), norm.get("currency", "THB"))),
        ("Surface", f'{norm["area_sqm"]:g} m²' if norm.get("area_sqm") else "—"),
        ("Prix/m²", f"{int(ppsqm):,} {norm.get('currency','THB')}".replace(",", " ") if ppsqm else "—"),
        ("Chambres", norm.get("bedrooms")),
        ("SDB", norm.get("bathrooms")),
        ("Type", "Vente" if norm.get("deal_type") == "sale" else "Location"),
        ("Quota", {"foreigner": "Foreigner", "thai": "Thai"}.get(norm.get("quota"), "—")),
        ("Quartier", norm.get("khet")),
    ]
    rows_html = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in rows
    )
    amen = norm.get("amenities") or []
    amen_html = (
        "<ul>" + "".join(f"<li>{_esc(a)}</li>" for a in amen) + "</ul>"
        if amen else '<p class="muted">— (enrichissement détail désactivé)</p>'
    )

    doc = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>{_esc(norm.get('title'))}</title>
<style>
  :root{{--bg:#0d0d12;--surface:#1d1830;--violet:#b026ff;--text:#ece9f5;--muted:#9b94b3;--line:#3b2a5c}}
  body{{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;padding:24px}}
  .card{{max-width:760px;margin:auto;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
  img{{width:100%;height:auto;display:block}}
  .body{{padding:20px}}
  h1{{font-size:20px;margin:0 0 4px}}
  h2{{font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--violet);margin:22px 0 8px}}
  a{{color:var(--violet)}} .muted{{color:var(--muted)}}
  table{{width:100%;border-collapse:collapse}}
  th,td{{text-align:left;padding:6px 0;border-bottom:1px solid var(--line);font-size:14px}}
  th{{color:var(--muted);font-weight:500;width:40%}}
</style></head><body>
<div class="card">
  {img_tag}
  <div class="body">
    <h1>{_esc(norm.get('title'))}</h1>
    <p class="muted"><a href="{_esc(norm.get('source_url'))}" target="_blank">source : {_esc(norm.get('source'))}</a></p>
    <h2>Le bien</h2>
    <table>{rows_html}</table>
    <h2>Amenities du condominium</h2>
    {amen_html}
    <h2>Proximité</h2>
    <p class="muted">École / métro / bus / CBD — calculé en Phase 4.</p>
  </div>
</div>
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path

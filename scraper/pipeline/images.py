"""images.py — Télécharge et optimise les images en webp 1024×768.

Cover-crop centré (remplit le cadre, sans bandes), conversion webp optimisée.
Stockées localement dans output/images/<listing_id>/<n>.webp (chemin renvoyé
= "storage_path", réutilisable tel quel côté Supabase Storage demain).
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from pipeline.fetch import Fetcher


def _safe_id(listing_id: str) -> str:
    return listing_id.replace(":", "_").replace("/", "_")


def process_images(fetcher: Fetcher, listing_id: str, urls: list[str],
                   out_root: Path, cfg: dict) -> list[dict]:
    """Retourne une liste de dicts {storage_path, width, height, ord}."""
    if not urls:
        return []
    w = cfg.get("width", 1024)
    h = cfg.get("height", 768)
    quality = cfg.get("quality", 80)
    max_n = cfg.get("max_per_listing", 1)

    dest_dir = out_root / "images" / _safe_id(listing_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for i, url in enumerate(urls[:max_n]):
        raw = fetcher.get_bytes(url)
        if not raw:
            continue
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            print(f"  image illisible ({url}): {e}")
            continue
        img = _cover_crop(img, w, h)
        out_path = dest_dir / f"{i}.webp"
        img.save(out_path, "WEBP", quality=quality, method=6)
        rel = out_path.relative_to(out_root).as_posix()
        results.append({"storage_path": rel, "width": w, "height": h, "ord": i})
    return results


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        # trop large → on rogne les côtés
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        # trop haut → on rogne haut/bas
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)

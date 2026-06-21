"""upload_images.py — Backfill : upload toutes les images locales (output/images)
vers Supabase Storage. Object path = chemin relatif (= storage_path en DB).

Usage : python upload_images.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline.storage import SupabaseStorage  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    import os
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    load_env()
    storage = SupabaseStorage.from_env()
    if not storage:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (scraper/.env)")

    files = sorted((OUTPUT / "images").rglob("*.webp"))
    if not files:
        sys.exit("Aucune image dans output/images")

    ok = 0
    for f in files:
        object_path = f.relative_to(OUTPUT).as_posix()  # images/<id>/N.webp
        if storage.upload(str(f), object_path):
            ok += 1
    print(f"✓ {ok}/{len(files)} images uploadées vers le bucket '{storage.bucket}'")


if __name__ == "__main__":
    main()

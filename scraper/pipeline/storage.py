"""storage.py — Upload des images vers Supabase Storage (bucket public).

Utilise l'API Storage REST avec la clé secret (service). Object path = chemin
relatif sous output/ (ex: "images/<id>/0.webp") → l'URL publique correspond à
ce que résout lib/image-url.ts côté app.
"""
from __future__ import annotations

import os
import requests


class SupabaseStorage:
    def __init__(self, url: str, service_key: str, bucket: str):
        self.base = url.rstrip("/")
        self.key = service_key
        self.bucket = bucket
        self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "SupabaseStorage | None":
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        bucket = os.environ.get("SUPABASE_BUCKET", "listings")
        if url and key:
            return cls(url, key, bucket)
        return None

    def upload(self, local_path: str, object_path: str, content_type: str = "image/webp") -> bool:
        url = f"{self.base}/storage/v1/object/{self.bucket}/{object_path}"
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            r = self.session.post(
                url,
                data=data,
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                timeout=30,
            )
            if r.status_code in (200, 201):
                return True
            print(f"  upload échec {object_path}: HTTP {r.status_code} {r.text[:120]}")
            return False
        except Exception as e:
            print(f"  upload erreur {object_path}: {e}")
            return False

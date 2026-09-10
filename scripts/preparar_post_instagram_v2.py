#!/usr/bin/env python3
"""Camada v2 com gate final obrigatório de imagem inédita."""
from __future__ import annotations

import hashlib
import json
import pathlib

import preparar_post_instagram_v2_core as core

_original_smart_main = core.smart.main


def _load_batch_post(batch_path: str = "instagram/fila/automatica/lote-atual.json"):
    batch = pathlib.Path(batch_path)
    if not batch.exists():
        return None, None
    try:
        data = json.loads(batch.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    rows = data if isinstance(data, list) else (data.get("items") or data.get("posts") or []) if isinstance(data, dict) else []
    if not rows:
        return None, None
    row = rows[0]
    post_path = row if isinstance(row, str) else (row.get("post_file") or row.get("file") or row.get("path") if isinstance(row, dict) else None)
    if not post_path:
        return None, None
    path = pathlib.Path(str(post_path))
    if not path.exists():
        return None, None
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, None


def _local_art_path(image_url: str) -> pathlib.Path | None:
    value = str(image_url or "").strip()
    if not value:
        return None
    root = str(getattr(core.base, "ROOT", "") or "")
    if root and value.startswith(root):
        path = pathlib.Path(value[len(root):])
        return path if path.exists() else None
    path = pathlib.Path(value)
    return path if path.exists() else None


def _sha256(path: pathlib.Path | None) -> str:
    if not path or not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _published_art_hashes() -> set[str]:
    ledger = core.base.load("instagram/publicados.json", {"published": []})
    hashes: set[str] = set()
    for row in ledger.get("published", []):
        if not isinstance(row, dict):
            continue
        post_file = pathlib.Path(str(row.get("post_file") or "").strip())
        if not post_file.exists():
            continue
        try:
            previous = json.loads(post_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        digest = _sha256(_local_art_path(previous.get("image_url")))
        if digest:
            hashes.add(digest)
    return hashes


def _current_image_identities(post: dict) -> set[str]:
    ids = set()
    for field in ("image_page_url", "source_page_url", "image_source_url", "image_url"):
        ident = core.smart.image_identity(post.get(field))
        if ident:
            ids.add(ident)
    return ids


def enforce_image_unique_gate() -> bool:
    """Falha fechado se a fonte visual ou a arte final já apareceu no ledger."""
    post_path, post = _load_batch_post()
    if not post_path or not isinstance(post, dict):
        print("IMAGE_UNIQUE_OK=false")
        print("reason=image_unique_failed")
        print("image_unique_detail=batch_or_post_missing")
        print("found=false")
        return False

    used_ids = core.smart.used_image_identities()
    current_ids = _current_image_identities(post)
    identity_collision = sorted(current_ids & used_ids)

    current_hash = _sha256(_local_art_path(post.get("image_url")))
    hash_collision = bool(current_hash and current_hash in _published_art_hashes())

    unique = not identity_collision and not hash_collision
    post["IMAGE_UNIQUE_OK"] = bool(unique)
    if unique:
        post["image_unique_reason"] = "source_and_render_not_previously_published"
    else:
        post["image_unique_reason"] = "previously_published_image"
        if identity_collision:
            post["image_duplicate_identity"] = identity_collision[0]
        if hash_collision:
            post["image_duplicate_render_sha256"] = current_hash
    post_path.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("IMAGE_UNIQUE_OK=" + str(unique).lower())
    if not unique:
        print("reason=image_unique_failed")
        print("image_unique_detail=source_or_render_already_used")
        print("found=false")
    return unique


def guarded_smart_main():
    result = _original_smart_main()
    if result != 0:
        return result
    return 0 if enforce_image_unique_gate() else 2


# O retry já existente entende image_unique_failed como falha recuperável,
# bloqueia temporariamente o item e procura outra combinação/pauta.
core.smart.main = guarded_smart_main


if __name__ == "__main__":
    result = core.run_with_quality_retry()
    core.normalize_image_gate()
    raise SystemExit(result)

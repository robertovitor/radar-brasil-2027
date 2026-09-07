"""Ajustes de runtime para o pipeline do Instagram.

Este módulo é carregado automaticamente pelo Python quando scripts/ está no
sys.path. Ele faz o seletor respeitar instagram/bloqueados.json, usado pelo
retry de qualidade do preparar_post_instagram_v2.py. Assim, um item reprovado
não volta a ser escolhido na tentativa seguinte da mesma execução.
"""
from __future__ import annotations

import json
import pathlib

try:
    import preparar_post_instagram_curado as _base
except Exception:
    _base = None


def _temporary_rejected_keys():
    path = pathlib.Path("instagram/bloqueados.json")
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, dict):
        return {
            str(key).strip()
            for key, value in data.items()
            if str(key).strip()
            and (
                value is True
                or (isinstance(value, dict) and value.get("reason") == "temporary_quality_retry")
            )
        }
    if isinstance(data, list):
        return {str(key).strip() for key in data if str(key).strip()}
    return set()


if _base is not None and not getattr(_base, "_quality_retry_filter_installed", False):
    _original_candidates = _base.candidates

    def _candidates_without_rejected(*args, **kwargs):
        ranked = _original_candidates(*args, **kwargs)
        rejected = _temporary_rejected_keys()
        if not rejected:
            return ranked
        filtered = [item for item in ranked if str(item.get("key") or "").strip() not in rejected]
        removed = len(ranked) - len(filtered)
        if removed:
            print(f"quality_retry_candidates_filtered={removed}")
            print("quality_retry_rejected_keys=" + ",".join(sorted(rejected)))
        return filtered

    _base.candidates = _candidates_without_rejected
    _base._quality_retry_filter_installed = True

"""Ajustes de runtime para o pipeline do Instagram.

Este módulo é carregado automaticamente pelo Python quando scripts/ está no
sys.path. Ele faz duas coisas:
1) impede que candidatos reprovados pelos gates voltem no retry da mesma rodada;
2) torna a consulta ao Wikimedia Commons mais estável, com cache, espaçamento
   entre chamadas e retry curto em HTTP 429 para preservar a busca de fotos.
"""
from __future__ import annotations

import json
import pathlib
import time
import urllib.error
import urllib.request

try:
    import preparar_post_instagram_curado as _base
    import preparar_post_instagram_sem_repetir_imagem as _smart
except Exception:
    _base = None
    _smart = None


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


# O Commons começou a responder 429 quando retries sucessivos faziam consultas
# em rajada. Mantemos um cache por URL e espaçamos apenas chamadas de rede reais.
# Em 429 fazemos até duas novas tentativas com backoff; 429 não bloqueia o provider
# inteiro imediatamente, porque isso empurrava toda a rodada para arte textual.
if _smart is not None and not getattr(_smart, "_commons_resilience_installed", False):
    _http_cache = {}
    _last_commons_call = 0.0
    _original_http_json = _smart.http_json

    def _resilient_http_json(url, source):
        nonlocal_holder = None  # mantém a função simples para Python 3.12
        global _last_commons_call

        cache_key = f"{source}:{url}"
        if cache_key in _http_cache:
            print(f"{source}_search_cache_hit=true")
            return _http_cache[cache_key]

        if source != "commons":
            data = _original_http_json(url, source)
            if data:
                _http_cache[cache_key] = data
            return data

        if _smart.REQUEST_BUDGET.get(source, 0) <= 0:
            return None

        # Mesmo que uma chamada anterior tenha marcado Commons como bloqueado por
        # um 429 transitório, esta camada assume o controle do backoff.
        _smart.SOURCE_BLOCKED[source] = False

        waits = (0.0, 3.0, 6.0)
        for attempt, retry_wait in enumerate(waits, start=1):
            if _smart.REQUEST_BUDGET.get(source, 0) <= 0:
                break
            if retry_wait:
                print(f"commons_rate_limit_retry_wait={int(retry_wait)}")
                time.sleep(retry_wait)

            elapsed = time.monotonic() - _last_commons_call
            min_interval = 1.25
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

            _smart.REQUEST_BUDGET[source] -= 1
            req = urllib.request.Request(url, headers={
                "User-Agent": "RadarBrasil2027/2.2 (GitHub robertovitor/radar-brasil-2027; contact via repository)",
                "Accept": "application/json",
            })
            try:
                _last_commons_call = time.monotonic()
                with urllib.request.urlopen(req, timeout=18) as response:
                    data = json.loads(response.read().decode("utf-8"))
                _http_cache[cache_key] = data
                if attempt > 1:
                    print(f"commons_rate_limit_recovered_attempt={attempt}")
                return data
            except urllib.error.HTTPError as exc:
                _last_commons_call = time.monotonic()
                print(f"commons_search_failed=HTTPError:{exc.code}")
                if exc.code == 429:
                    # Tenta novamente após backoff; não mata o provider inteiro.
                    continue
                if exc.code == 403:
                    _smart.SOURCE_BLOCKED[source] = True
                return None
            except Exception as exc:
                _last_commons_call = time.monotonic()
                print(f"commons_search_failed={type(exc).__name__}")
                return None

        print("commons_rate_limit_exhausted=true")
        return None

    _smart.http_json = _resilient_http_json
    _smart._commons_resilience_installed = True

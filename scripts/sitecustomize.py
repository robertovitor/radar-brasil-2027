"""Ajustes de runtime para o pipeline do Instagram.

Este módulo é carregado automaticamente pelo Python quando scripts/ está no
sys.path. Ele faz quatro coisas:
1) impede que candidatos reprovados pelos gates voltem no retry da mesma rodada;
2) bloqueia notícias com mais de 30 dias antes da seleção para o Instagram;
3) torna a consulta ao Wikimedia Commons mais estável, com cache, espaçamento
   entre chamadas e retry curto em HTTP 429 para preservar a busca de fotos;
4) exige confirmação da entidade quando a pauta é sobre a Seleção Brasileira feminina.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
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


def _news_date_from_url(url):
    """Usa a data editorial explícita no URL quando ela existir."""
    match = re.search(
        r"/(20\d{2})[/-](0[1-9]|1[0-2])[/-]([0-2]\d|3[01])(?:/|\b)",
        str(url or "").strip(),
    )
    if not match:
        return None
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _news_date(item):
    from_url = _news_date_from_url(item.get("Link"))
    if from_url is not None:
        return from_url
    try:
        return dt.date.fromisoformat(str(item.get("Data") or "").strip()[:10])
    except (TypeError, ValueError):
        return None


if _base is not None and not getattr(_base, "_quality_retry_filter_installed", False):
    _original_candidates = _base.candidates

    def _candidates_without_rejected(*args, **kwargs):
        ranked = _original_candidates(*args, **kwargs)
        today = dt.datetime.now(dt.timezone.utc).date()
        cutoff = today - dt.timedelta(days=30)
        fresh_ranked = []
        stale_removed = 0
        for item in ranked:
            if str(item.get("type") or "").strip().casefold() != "noticia":
                fresh_ranked.append(item)
                continue
            key = str(item.get("key") or "").strip()
            url = key[len("instagram:noticia:"):] if key.startswith("instagram:noticia:") else ""
            effective = _news_date_from_url(url) or item.get("date")
            if isinstance(effective, dt.datetime):
                effective = effective.date()
            if isinstance(effective, dt.date) and effective < cutoff:
                stale_removed += 1
                print(
                    "stale_news_blocked="
                    + str(item.get("title") or "").strip()
                    + f" | effective_date={effective.isoformat()} | cutoff={cutoff.isoformat()}"
                )
                continue
            fresh_ranked.append(item)
        ranked = fresh_ranked
        if stale_removed:
            print(f"instagram_stale_news_filtered={stale_removed}")
            print("instagram_freshness_guard=max_30_days")

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


# Gate de entidade: uma foto genericamente ligada a futebol feminino não pode
# ilustrar uma pauta explicitamente sobre a Seleção Brasileira feminina.
def _brazil_wnt_item(item):
    if _base is None:
        return False
    text = _base.norm(" ".join([
        _base.clean(item.get("title")),
        _base.clean(item.get("search_context")),
    ]))
    brazil = bool(re.search(r"\b(brasil|brasileir[ao])\b", text))
    selection = bool(re.search(r"\b(selecao|national team)\b", text))
    female = bool(re.search(r"\b(feminin[ao]|women|womens|woman|female)\b", text))
    return brazil and selection and female


def _brazil_wnt_confirmed(descriptor):
    if _base is None:
        return False
    d = _base.norm(descriptor)
    explicit = (
        r"\bselecao brasileira feminina\b",
        r"\bselecao feminina brasileira\b",
        r"\bbrazil women(?:s)? national (?:football|soccer) team\b",
        r"\bbrazilian women(?:s)? national (?:football|soccer) team\b",
        r"\bbrazil women(?:s)? (?:football|soccer) team\b",
    )
    if any(re.search(pattern, d) for pattern in explicit):
        return True
    brazil = bool(re.search(r"\b(brasil|brazil|brasileir[ao]|brazilian)\b", d))
    selection = bool(re.search(r"\b(selecao|national team)\b", d))
    female = bool(re.search(r"\b(feminin[ao]|women|womens|woman|female)\b", d))
    return brazil and selection and female


if _base is not None and not getattr(_base, "_brazil_wnt_entity_gate_installed", False):
    _original_semantic_image_ok = _base.semantic_image_ok
    _original_curated_image_policy_ok = _base.curated_image_policy_ok

    def _strict_semantic_image_ok(item, page, meta, query):
        ok, reason = _original_semantic_image_ok(item, page, meta, query)
        if not ok or not _brazil_wnt_item(item):
            return ok, reason
        descriptor = _base.commons_descriptor(page, meta)
        if not _brazil_wnt_confirmed(descriptor):
            return False, "brazil_wnt_entity_not_confirmed"
        return True, "brazil_wnt_entity_confirmed"

    def _strict_curated_image_policy_ok(item, image):
        ok, reason = _original_curated_image_policy_ok(item, image)
        if not ok or not _brazil_wnt_item(item):
            return ok, reason
        descriptor = " ".join(filter(None, [
            _base.clean(image.get("source_page_url")),
            _base.clean(image.get("image_source_url")),
            _base.clean(image.get("justificativa")),
            _base.clean(image.get("visual_description")),
            _base.clean(image.get("tags")),
        ]))
        if not _brazil_wnt_confirmed(descriptor):
            return False, "brazil_wnt_entity_not_confirmed"
        return True, "brazil_wnt_entity_confirmed"

    _base.semantic_image_ok = _strict_semantic_image_ok
    _base.curated_image_policy_ok = _strict_curated_image_policy_ok
    _base._brazil_wnt_entity_gate_installed = True
    print("instagram_entity_image_gate=brazil_wnt_strict")


if _smart is not None and not getattr(_smart, "_commons_resilience_installed", False):
    _http_cache = {}
    _last_commons_call = 0.0
    _original_http_json = _smart.http_json

    def _resilient_http_json(url, source):
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

#!/usr/bin/env python3
"""Publica um post aprovado no Instagram com idempotência, reconciliação remota e retries seguros."""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata

GRAPH_VERSION = os.getenv("INSTAGRAM_GRAPH_VERSION", "v25.0")
FACEBOOK_GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
INSTAGRAM_GRAPH_ROOT = f"https://graph.instagram.com/{GRAPH_VERSION}"


class InstagramError(RuntimeError):
    def __init__(self, message: str, code=None, subcode=None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


def request_json(method: str, path: str, token: str, params: dict | None = None, graph_root: str = FACEBOOK_GRAPH_ROOT) -> dict:
    data = dict(params or {})
    data["access_token"] = token
    encoded = urllib.parse.urlencode(data).encode()
    url = f"{graph_root}/{path.lstrip('/')}"
    req = urllib.request.Request(url if method == "POST" else f"{url}?{encoded.decode()}", data=encoded if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            detail = json.loads(body).get("error", {})
            message = detail.get("message", body)
            code = detail.get("code")
            subcode = detail.get("error_subcode")
            raise InstagramError(f"Meta API: {message} (code={code}, subcode={subcode})", code=code, subcode=subcode) from None
        except json.JSONDecodeError:
            raise InstagramError(f"Meta API HTTP {exc.code}: {body[:500]}", code=exc.code) from None


def discover_instagram_user(token: str) -> tuple[str, str, str]:
    configured = os.getenv("INSTAGRAM_USER_ID", "").strip()
    try:
        profile = request_json("GET", configured or "me", token, {"fields": "id,user_id,username,account_type"}, graph_root=INSTAGRAM_GRAPH_ROOT)
        instagram_id = profile.get("user_id") or profile.get("id")
        if instagram_id:
            return INSTAGRAM_GRAPH_ROOT, str(instagram_id), str(profile.get("username", ""))
    except InstagramError:
        pass
    if configured:
        profile = request_json("GET", configured, token, {"fields": "id,username"}, graph_root=FACEBOOK_GRAPH_ROOT)
        return FACEBOOK_GRAPH_ROOT, configured, str(profile.get("username", ""))
    pages = request_json("GET", "me/accounts", token, {"fields": "id,name,instagram_business_account{id,username}", "limit": "100"}, graph_root=FACEBOOK_GRAPH_ROOT)
    accounts = []
    for page in pages.get("data", []):
        ig = page.get("instagram_business_account")
        if ig and ig.get("id"):
            accounts.append((str(ig["id"]), str(ig.get("username", ""))))
    if not accounts:
        raise InstagramError("Nenhuma conta profissional do Instagram foi encontrada no token. Confirme o produto de login e as permissões de publicação.")
    if len(accounts) > 1:
        names = ", ".join(username or user_id for user_id, username in accounts)
        raise InstagramError(f"O token acessa mais de uma conta ({names}); defina INSTAGRAM_USER_ID.")
    user_id, username = accounts[0]
    return FACEBOOK_GRAPH_ROOT, user_id, username


def load_json(path: pathlib.Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stable_key(post: dict) -> str:
    explicit = str(post.get("idempotency_key") or post.get("id") or "").strip()
    if explicit:
        return explicit
    canonical = json.dumps({"image_url": post.get("image_url"), "caption": post.get("caption")}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


DEDUP_IGNORED = {"copa", "mundo", "mundial", "feminina", "feminino", "fifa", "2027", "brasil", "noticia", "evento", "para", "com", "sem", "uma", "das", "dos", "que", "como", "novo", "nova", "confirma", "prepara", "preparam", "destaca", "adequacoes"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def post_title(post: dict) -> str:
    caption = str(post.get("caption") or "").strip()
    return re.sub(r"^[^\wÀ-ÿ]+", "", caption.splitlines()[0]).strip() if caption else ""


def title_tokens(value: str) -> set[str]:
    return {token[:7] for token in re.findall(r"[a-z0-9]+", normalize_text(value)) if len(token) >= 3 and token not in DEDUP_IGNORED}


def same_topic(a: str, b: str) -> bool:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = title_tokens(a), title_tokens(b)
    if len(ta) < 3 or len(tb) < 3:
        return False
    shared = len(ta & tb)
    coverage = shared / min(len(ta), len(tb))
    union = shared / len(ta | tb)
    sequence = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return (shared >= 3 and coverage >= 0.80) or (shared >= 4 and (coverage >= 0.62 or union >= 0.50 or sequence >= 0.72))


def guard_semantic_duplicate(post: dict, published: list[dict]) -> None:
    current = post_title(post)
    if not current:
        return
    for item in published:
        path = pathlib.Path(str(item.get("post_file") or ""))
        if not path.exists():
            continue
        try:
            previous = load_json(path, {})
        except (json.JSONDecodeError, OSError):
            continue
        old_title = post_title(previous)
        if old_title and same_topic(current, old_title):
            raise InstagramError(f"Duplicidade semântica bloqueada: '{current}' repete a pauta '{old_title}'.")


def validate_post(post: dict, require_approval: bool) -> None:
    missing = [field for field in ("image_url", "caption") if not str(post.get(field, "")).strip()]
    if missing:
        raise InstagramError("Campos obrigatórios ausentes: " + ", ".join(missing))
    if not str(post["image_url"]).startswith("https://"):
        raise InstagramError("image_url precisa ser uma URL HTTPS pública.")
    if len(str(post["caption"])) > 2200:
        raise InstagramError("A legenda excede 2.200 caracteres.")
    if require_approval and post.get("approved") is not True:
        raise InstagramError("Post bloqueado: defina approved como true após revisão editorial.")


def wait_until_ready(container_id: str, token: str, graph_root: str) -> None:
    for attempt in range(30):
        status = request_json("GET", container_id, token, {"fields": "status_code,status"}, graph_root=graph_root)
        code = str(status.get("status_code") or "").upper()
        if code == "FINISHED":
            if attempt:
                time.sleep(5)
            return
        if code in {"ERROR", "EXPIRED"}:
            raise InstagramError(f"Container não publicável: {status}")
        time.sleep(4)
    raise InstagramError("Tempo esgotado aguardando o processamento da imagem.")


def recent_remote_media(user_id: str, token: str, graph_root: str) -> list[dict]:
    try:
        data = request_json("GET", f"{user_id}/media", token, {"fields": "id,caption,timestamp", "limit": "25"}, graph_root=graph_root)
        return [x for x in data.get("data", []) if isinstance(x, dict)]
    except InstagramError as exc:
        print(f"remote_reconciliation_warning={exc}")
        return []


def reconcile_existing(post: dict, user_id: str, token: str, graph_root: str) -> str | None:
    caption = str(post.get("caption") or "").strip()
    title = post_title(post)
    now = dt.datetime.now(dt.timezone.utc)
    for item in recent_remote_media(user_id, token, graph_root):
        remote_caption = str(item.get("caption") or "").strip()
        raw_ts = str(item.get("timestamp") or "").strip()
        if raw_ts:
            try:
                ts = dt.datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.timezone.utc)
                if now - ts.astimezone(dt.timezone.utc) > dt.timedelta(days=7):
                    continue
            except ValueError:
                pass
        exact = bool(caption and remote_caption and caption == remote_caption)
        topic_match = bool(title and remote_caption and same_topic(title, post_title({"caption": remote_caption})))
        if exact or topic_match:
            media_id = str(item.get("id") or "").strip()
            if media_id:
                print(f"remote_existing_media_found={media_id}")
                return media_id
    return None


def append_ledger(args, published: list[dict], key: str, media_id: str, creation_id: str | None = None, reconciled: bool = False) -> None:
    if any(str(item.get("key") or "") == key for item in published):
        return
    row = {
        "key": key,
        "post_file": str(args.post),
        "instagram_media_id": str(media_id),
        "published_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    if creation_id:
        row["creation_id"] = str(creation_id)
    if reconciled:
        row["reconciled_from_remote"] = True
    published.append(row)
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.write_text(json.dumps({"published": published}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish_with_retry(user_id: str, creation_id: str, token: str, graph_root: str, post: dict) -> str:
    last_error = None
    for attempt in range(1, 5):
        try:
            response = request_json("POST", f"{user_id}/media_publish", token, {"creation_id": creation_id}, graph_root=graph_root)
            media_id = str(response.get("id") or "").strip()
            if not media_id:
                raise InstagramError("A Meta não retornou o ID da publicação.")
            return media_id
        except InstagramError as exc:
            last_error = exc
            if exc.code == 9007 or exc.subcode == 2207027:
                print(f"media_publish_retry={attempt};reason=media_id_not_available")
                time.sleep(10 * attempt)
                try:
                    wait_until_ready(creation_id, token, graph_root)
                except InstagramError:
                    pass
                existing = reconcile_existing(post, user_id, token, graph_root)
                if existing:
                    return existing
                continue
            existing = reconcile_existing(post, user_id, token, graph_root)
            if existing:
                return existing
            raise
    existing = reconcile_existing(post, user_id, token, graph_root)
    if existing:
        return existing
    raise last_error or InstagramError("Falha desconhecida em media_publish.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", required=True, type=pathlib.Path)
    parser.add_argument("--ledger", default="instagram/publicados.json", type=pathlib.Path)
    parser.add_argument("--blocked", default="instagram/bloqueados-publicacao.json", type=pathlib.Path)
    parser.add_argument("--mode", choices=("validate", "dry-run", "publish"), default="validate")
    parser.add_argument("--min-hours-between", type=float, default=0)
    parser.add_argument("--max-per-24h", type=int, default=0)
    args = parser.parse_args()

    post = load_json(args.post, {})
    validate_post(post, require_approval=args.mode == "publish")
    key = stable_key(post)
    ledger = load_json(args.ledger, {"published": []})
    published = ledger.get("published", [])
    blocked = load_json(args.blocked, {"blocked_keys": []})
    if key in {str(value).strip() for value in blocked.get("blocked_keys", [])}:
        raise InstagramError(f"Publicação bloqueada preventivamente: {key}.")
    if any(item.get("key") == key for item in published):
        raise InstagramError(f"Duplicidade bloqueada: {key} já consta em {args.ledger}.")
    guard_semantic_duplicate(post, published)

    if args.mode == "validate":
        print(f"Validação local concluída; chave: {key}; nenhum secret foi carregado.")
        return 0

    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if token.startswith("INSTAGRAM_ACCESS_TOKEN="):
        token = token.split("=", 1)[1].strip()
    token = token.strip().strip('"').strip("'").strip()
    if not token:
        raise InstagramError("Secret INSTAGRAM_ACCESS_TOKEN ausente.")

    if args.mode == "publish" and published:
        now = dt.datetime.now(dt.timezone.utc)
        recent_times = []
        for item in published:
            raw = str(item.get("published_at", "")).strip()
            if not raw:
                continue
            try:
                parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                recent_times.append(parsed.astimezone(dt.timezone.utc))
            except ValueError:
                continue
        if args.max_per_24h > 0:
            in_last_day = [value for value in recent_times if now - value < dt.timedelta(hours=24)]
            if len(in_last_day) >= args.max_per_24h:
                raise InstagramError(f"Limite editorial atingido: {len(in_last_day)} publicação(ões) nas últimas 24 horas.")
        if args.min_hours_between > 0 and recent_times:
            elapsed = now - max(recent_times)
            minimum = dt.timedelta(hours=args.min_hours_between)
            if elapsed < minimum:
                raise InstagramError(f"Intervalo editorial ainda não cumprido; aguarde cerca de {minimum - elapsed}.")

    graph_root, user_id, username = discover_instagram_user(token)
    print(f"Conta validada: @{username or user_id}; chave: {key}; modo: {args.mode}")
    if args.mode == "dry-run":
        print("Teste concluído sem criar publicação.")
        return 0

    existing = reconcile_existing(post, user_id, token, graph_root)
    if existing:
        append_ledger(args, published, key, existing, reconciled=True)
        print(f"Publicação já existia na Meta e foi reconciliada: media_id={existing}")
        return 0

    container = request_json("POST", f"{user_id}/media", token, {"image_url": post["image_url"], "caption": post["caption"]}, graph_root=graph_root)
    creation_id = str(container.get("id") or "").strip()
    if not creation_id:
        raise InstagramError("A Meta não retornou o ID do contêiner.")
    print(f"creation_id={creation_id}")
    wait_until_ready(creation_id, token, graph_root)
    media_id = publish_with_retry(user_id, creation_id, token, graph_root, post)
    append_ledger(args, published, key, media_id, creation_id=creation_id)
    print(f"Publicado com sucesso: media_id={media_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstagramError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)

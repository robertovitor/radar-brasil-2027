#!/usr/bin/env python3
"""Publica um post aprovado no Instagram com proteção contra duplicidade."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_VERSION = os.getenv("INSTAGRAM_GRAPH_VERSION", "v25.0")
FACEBOOK_GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
INSTAGRAM_GRAPH_ROOT = f"https://graph.instagram.com/{GRAPH_VERSION}"


class InstagramError(RuntimeError):
    pass


def request_json(
    method: str,
    path: str,
    token: str,
    params: dict | None = None,
    graph_root: str = FACEBOOK_GRAPH_ROOT,
) -> dict:
    data = dict(params or {})
    data["access_token"] = token
    encoded = urllib.parse.urlencode(data).encode()
    url = f"{graph_root}/{path.lstrip('/')}"
    req = urllib.request.Request(
        url if method == "POST" else f"{url}?{encoded.decode()}",
        data=encoded if method == "POST" else None,
        method=method,
    )
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
            raise InstagramError(f"Meta API: {message} (code={code}, subcode={subcode})") from None
        except json.JSONDecodeError:
            raise InstagramError(f"Meta API HTTP {exc.code}: {body[:500]}") from None


def discover_instagram_user(token: str) -> tuple[str, str, str]:
    configured = os.getenv("INSTAGRAM_USER_ID", "").strip()

    # Token emitido pelo produto "Instagram API with Instagram Login".
    try:
        profile = request_json(
            "GET",
            configured or "me",
            token,
            {"fields": "id,user_id,username,account_type"},
            graph_root=INSTAGRAM_GRAPH_ROOT,
        )
        instagram_id = profile.get("user_id") or profile.get("id")
        if instagram_id:
            return INSTAGRAM_GRAPH_ROOT, str(instagram_id), str(profile.get("username", ""))
    except InstagramError:
        pass

    # Token emitido pelo produto "Instagram API with Facebook Login".
    if configured:
        profile = request_json(
            "GET", configured, token, {"fields": "id,username"},
            graph_root=FACEBOOK_GRAPH_ROOT,
        )
        return FACEBOOK_GRAPH_ROOT, configured, str(profile.get("username", ""))

    pages = request_json(
        "GET",
        "me/accounts",
        token,
        {"fields": "id,name,instagram_business_account{id,username}", "limit": "100"},
        graph_root=FACEBOOK_GRAPH_ROOT,
    )
    accounts = []
    for page in pages.get("data", []):
        ig = page.get("instagram_business_account")
        if ig and ig.get("id"):
            accounts.append((str(ig["id"]), str(ig.get("username", ""))))
    if not accounts:
        raise InstagramError(
            "Nenhuma conta profissional do Instagram foi encontrada no token. "
            "Confirme o produto de login e as permissões de publicação."
        )
    if len(accounts) > 1:
        names = ", ".join(username or user_id for user_id, username in accounts)
        raise InstagramError(
            f"O token acessa mais de uma conta ({names}); defina INSTAGRAM_USER_ID."
        )
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
    canonical = json.dumps(
        {"image_url": post.get("image_url"), "caption": post.get("caption")},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


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
    for _ in range(20):
        status = request_json(
            "GET", container_id, token, {"fields": "status_code,status"},
            graph_root=graph_root,
        )
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            raise InstagramError(f"Container não publicável: {status}")
        time.sleep(3)
    raise InstagramError("Tempo esgotado aguardando o processamento da imagem.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post", required=True, type=pathlib.Path)
    parser.add_argument("--ledger", default="instagram/publicados.json", type=pathlib.Path)
    parser.add_argument("--mode", choices=("validate", "dry-run", "publish"), default="validate")
    parser.add_argument("--min-hours-between", type=float, default=0)
    parser.add_argument("--max-per-24h", type=int, default=0)
    args = parser.parse_args()

    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if token.startswith("INSTAGRAM_ACCESS_TOKEN="):
        token = token.split("=", 1)[1].strip()
    token = token.strip().strip('"').strip("'").strip()
    if not token:
        raise InstagramError("Secret INSTAGRAM_ACCESS_TOKEN ausente.")

    post = load_json(args.post, {})
    validate_post(post, require_approval=args.mode == "publish")
    key = stable_key(post)
    ledger = load_json(args.ledger, {"published": []})
    published = ledger.get("published", [])
    if any(item.get("key") == key for item in published):
        raise InstagramError(f"Duplicidade bloqueada: {key} já consta em {args.ledger}.")

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
                raise InstagramError(
                    f"Limite editorial atingido: {len(in_last_day)} publicação(ões) nas últimas 24 horas."
                )
        if args.min_hours_between > 0 and recent_times:
            elapsed = now - max(recent_times)
            minimum = dt.timedelta(hours=args.min_hours_between)
            if elapsed < minimum:
                remaining = minimum - elapsed
                raise InstagramError(
                    f"Intervalo editorial ainda não cumprido; aguarde cerca de {remaining}."
                )

    graph_root, user_id, username = discover_instagram_user(token)
    print(f"Conta validada: @{username or user_id}; chave: {key}; modo: {args.mode}")

    if args.mode in {"validate", "dry-run"}:
        print("Teste concluído sem criar publicação.")
        return 0

    container = request_json(
        "POST",
        f"{user_id}/media",
        token,
        {"image_url": post["image_url"], "caption": post["caption"]},
        graph_root=graph_root,
    )
    creation_id = container.get("id")
    if not creation_id:
        raise InstagramError("A Meta não retornou o ID do contêiner.")
    wait_until_ready(str(creation_id), token, graph_root)
    published_media = request_json(
        "POST", f"{user_id}/media_publish", token, {"creation_id": creation_id},
        graph_root=graph_root,
    )
    media_id = published_media.get("id")
    if not media_id:
        raise InstagramError("A Meta não retornou o ID da publicação.")

    published.append(
        {
            "key": key,
            "post_file": str(args.post),
            "instagram_media_id": str(media_id),
            "published_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.write_text(
        json.dumps({"published": published}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Publicado com sucesso: media_id={media_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstagramError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)

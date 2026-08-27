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
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"


class InstagramError(RuntimeError):
    pass


def request_json(method: str, path: str, token: str, params: dict | None = None) -> dict:
    data = dict(params or {})
    data["access_token"] = token
    encoded = urllib.parse.urlencode(data).encode()
    url = f"{GRAPH_ROOT}/{path.lstrip('/')}"
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


def discover_instagram_user(token: str) -> tuple[str, str]:
    configured = os.getenv("INSTAGRAM_USER_ID", "").strip()
    if configured:
        profile = request_json("GET", configured, token, {"fields": "id,username"})
        return configured, profile.get("username", "")

    # Token obtido via Instagram Login.
    try:
        profile = request_json("GET", "me", token, {"fields": "id,username,account_type"})
        if profile.get("id") and profile.get("username"):
            return str(profile["id"]), str(profile["username"])
    except InstagramError:
        pass

    # Token obtido via Facebook Login e Página vinculada.
    pages = request_json(
        "GET",
        "me/accounts",
        token,
        {"fields": "id,name,instagram_business_account{id,username}", "limit": "100"},
    )
    accounts = []
    for page in pages.get("data", []):
        ig = page.get("instagram_business_account")
        if ig and ig.get("id"):
            accounts.append((str(ig["id"]), str(ig.get("username", ""))))
    if not accounts:
        raise InstagramError(
            "Nenhuma conta profissional do Instagram foi encontrada no token. "
            "Vincule o perfil a uma Página ou defina o secret INSTAGRAM_USER_ID."
        )
    if len(accounts) > 1:
        names = ", ".join(username or user_id for user_id, username in accounts)
        raise InstagramError(
            f"O token acessa mais de uma conta ({names}); defina INSTAGRAM_USER_ID."
        )
    return accounts[0]


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


def wait_until_ready(container_id: str, token: str) -> None:
    for _ in range(20):
        status = request_json("GET", container_id, token, {"fields": "status_code,status"})
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

    user_id, username = discover_instagram_user(token)
    print(f"Conta validada: @{username or user_id}; chave: {key}; modo: {args.mode}")

    if args.mode in {"validate", "dry-run"}:
        print("Teste concluído sem criar publicação.")
        return 0

    container = request_json(
        "POST",
        f"{user_id}/media",
        token,
        {"image_url": post["image_url"], "caption": post["caption"]},
    )
    creation_id = container.get("id")
    if not creation_id:
        raise InstagramError("A Meta não retornou o ID do contêiner.")
    wait_until_ready(str(creation_id), token)
    published_media = request_json(
        "POST", f"{user_id}/media_publish", token, {"creation_id": creation_id}
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

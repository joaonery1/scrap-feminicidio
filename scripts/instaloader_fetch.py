"""
scripts/instaloader_fetch.py

Fetches posts from Instagram profiles using session cookie,
filters by feminicide-related keywords, and outputs JSONL.

Usage:
    python scripts/instaloader_fetch.py --output /tmp/ig_posts.jsonl
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=False)
    except ImportError:
        pass

try:
    import requests
except ImportError:
    print("requests is not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

KEYWORDS = [
    "feminicídio", "feminicidio", "feminic1d", "feminic1dio",
    "femicídio", "femicidio",
    "mulher morta", "mulher m0rta", "mulher m4t4",
    "esposa morta", "esposa m0rta",
    "companheira morta", "companheira m0rta",
    "namorada morta", "namorada m0rta",
    "mulher assassinada",
    "mulher esfaqueada", "mulher baleada",
    "mata esposa", "mata a esposa",
    "mata a companheira", "mata a namorada",
    "mata a mulher", "matou a esposa",
    "matou a companheira", "matou a mulher",
    "m4t4 esposa", "m4t4 a esposa",
    "fem1n1c", "f3minicid",
]

NEGATIVE_KEYWORDS = [
    "saiba como acessar", "como se inscrever", "inscrições abertas",
    "assistência financeira", "programa oferta", "acesse o link",
    "link na bio", "clique no link", "palestra", "capacitação",
    "campanha de", "dia internacional", "comemorar", "celebrar",
    "homem morto", "homem m0rto", "homem é morto",
    "jovem morto", "jovem é morto", "jovem m0rto",
    "trabalhador morto", "motoqueiro morto", "motoboy morto",
    "homem assassinado", "rapaz morto",
]

TARGET_PROFILES = ["gordinhodopovose", "dougtvnews"]
MAX_POSTS = 50


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("4", "a").replace("3", "e")
        .replace("1", "i").replace("0", "o")
        .replace("#", "a").replace("@", "a").replace("$", "s")
    )


def is_relevant(caption: str) -> bool:
    if not caption:
        return False
    normalized = _normalize(caption)
    if not any(_normalize(kw) in normalized for kw in KEYWORDS):
        return False
    if any(_normalize(nkw) in normalized for nkw in NEGATIVE_KEYWORDS):
        return False
    return True


def make_session(session_id: str) -> requests.Session:
    s = requests.Session()
    s.cookies.set("sessionid", unquote(session_id), domain=".instagram.com")
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-IG-App-ID": "936619743392459",
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://www.instagram.com/",
    })
    return s


def get_user_id(session: requests.Session, username: str) -> str:
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    r = session.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    user = data.get("data", {}).get("user", {})
    user_id = user.get("id")
    if not user_id:
        raise ValueError(f"Perfil '{username}' não encontrado ou privado.")
    return user_id


def get_posts(session: requests.Session, user_id: str, max_posts: int):
    posts = []
    next_max_id = None

    while len(posts) < max_posts:
        url = f"https://i.instagram.com/api/v1/feed/user/{user_id}/"
        params = {"count": 12}
        if next_max_id:
            params["max_id"] = next_max_id

        r = session.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        items = data.get("items", [])
        if not items:
            break

        posts.extend(items)

        if not data.get("more_available"):
            break
        next_max_id = data.get("next_max_id")
        if not next_max_id:
            break

        time.sleep(1)

    return posts[:max_posts]


def fetch_profile(session: requests.Session, username: str) -> list:
    print(f"Buscando perfil '{username}'...")
    try:
        user_id = get_user_id(session, username)
        print(f"user_id: {user_id}")
    except Exception as exc:
        print(f"Erro ao buscar perfil '{username}': {exc}", file=sys.stderr)
        return []

    print(f"Buscando posts de '{username}'...")
    try:
        items = get_posts(session, user_id, MAX_POSTS)
    except Exception as exc:
        print(f"Erro ao buscar posts de '{username}': {exc}", file=sys.stderr)
        return []

    relevant = []
    for item in items:
        caption_data = item.get("caption") or {}
        caption = caption_data.get("text", "") if isinstance(caption_data, dict) else ""
        if not is_relevant(caption):
            continue

        taken_at = item.get("taken_at")
        published_at = datetime.fromtimestamp(taken_at, tz=timezone.utc).isoformat() if taken_at else None
        code = item.get("code") or item.get("shortcode", "")
        url = f"https://www.instagram.com/p/{code}/" if code else ""

        relevant.append({
            "url": url,
            "title": caption[:200],
            "body": caption,
            "published_at": published_at,
        })

    return relevant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/ig_posts.jsonl")
    args = parser.parse_args()

    session_id = os.getenv("IG_SESSION_ID", "")
    if not session_id:
        print("IG_SESSION_ID é obrigatório no .env", file=sys.stderr)
        sys.exit(1)

    session = make_session(session_id)

    all_posts = []
    for username in TARGET_PROFILES:
        posts = fetch_profile(session, username)
        all_posts.extend(posts)
        if posts:
            print(f"{len(posts)} posts relevantes de '{username}'")

    if not all_posts:
        print("Nenhum post relevante encontrado.")
        sys.exit(0)

    with open(args.output, "w", encoding="utf-8") as f:
        for record in all_posts:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_posts)} relevant posts to {args.output}")


if __name__ == "__main__":
    main()

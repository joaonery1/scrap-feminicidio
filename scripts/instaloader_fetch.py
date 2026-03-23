"""
scripts/instaloader_fetch.py

Fetches posts from an Instagram profile using instaloader session + Instagram API v1,
filters by feminicide-related keywords, and outputs JSONL.

Usage:
    python3 scripts/instaloader_fetch.py --output /tmp/ig_posts.jsonl
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Carrega .env da raiz do projeto
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass

KEYWORDS = [
    "feminicídio",
    "feminicidio",
    "mulher morta",
    "violência doméstica",
    "violencia domestica",
]

TARGET_PROFILE = "gordinhodopovose"
MAX_POSTS = 50  # últimos posts a verificar


def is_relevant(caption: str) -> bool:
    if not caption:
        return False
    caption_lower = caption.lower()
    return any(kw.lower() in caption_lower for kw in KEYWORDS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/ig_posts.jsonl")
    args = parser.parse_args()

    try:
        import instaloader
    except ImportError:
        print("instaloader is not installed. Run: pip install instaloader", file=sys.stderr)
        sys.exit(1)

    ig_user = os.getenv("IG_USER", "")
    ig_password = os.getenv("IG_PASSWORD", "")

    if not ig_user or not ig_password:
        print("IG_USER e IG_PASSWORD são obrigatórios.", file=sys.stderr)
        sys.exit(1)

    L = instaloader.Instaloader(quiet=True)
    try:
        L.login(ig_user, ig_password)
    except instaloader.exceptions.BadCredentialsException:
        print("Login falhou: credenciais inválidas.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Erro no login: {exc}", file=sys.stderr)
        sys.exit(1)

    # Busca user_id via API v1 (Profile.from_username está quebrado com a API atual)
    session = L.context._session
    headers = {
        "User-Agent": "Instagram 219.0.0.12.117 Android",
        "X-IG-App-ID": "936619743392459",
    }

    try:
        r = session.get(
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={TARGET_PROFILE}",
            headers=headers,
        )
        r.raise_for_status()
        user_data = r.json().get("data", {}).get("user", {})
        user_id = user_data.get("id")
        if not user_id:
            print(f"Perfil '{TARGET_PROFILE}' não encontrado.", file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f"Erro ao buscar perfil: {exc}", file=sys.stderr)
        sys.exit(1)

    # Cria Profile via ID (bypassa from_username que está quebrado)
    relevant_posts = []
    try:
        profile = instaloader.Profile.from_id(L.context, user_id)
        count = 0
        for post in profile.get_posts():
            if count >= MAX_POSTS:
                break
            count += 1
            caption = post.caption or ""
            if not is_relevant(caption):
                continue
            published_at = post.date_utc.replace(tzinfo=timezone.utc).isoformat()
            url = f"https://www.instagram.com/p/{post.shortcode}/"
            relevant_posts.append({
                "url": url,
                "title": caption[:200],
                "body": caption,
                "published_at": published_at,
            })
    except Exception as exc:
        print(f"Erro ao buscar posts: {exc}", file=sys.stderr)
        sys.exit(1)

    if not relevant_posts:
        print("Nenhum post relevante encontrado.", file=sys.stderr)
        sys.exit(0)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            for record in relevant_posts:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"Erro ao escrever arquivo: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {len(relevant_posts)} relevant posts to {args.output}")


if __name__ == "__main__":
    main()

"""
scripts/instaloader_fetch.py

Fetches posts from an Instagram profile using instaloader,
filters by feminicide-related keywords, and outputs JSONL.

Usage:
    python3 scripts/instaloader_fetch.py --output /tmp/ig_posts.jsonl
"""

import argparse
import json
import os
import sys
from datetime import timezone


KEYWORDS = [
    "feminicídio",
    "feminicidio",
    "mulher morta",
    "violência doméstica",
    "violencia domestica",
]

TARGET_PROFILE = "gordinhodopovose"


def is_relevant(caption: str) -> bool:
    if not caption:
        return False
    caption_lower = caption.lower()
    return any(kw.lower() in caption_lower for kw in KEYWORDS)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Instagram posts and output relevant ones as JSONL."
    )
    parser.add_argument(
        "--output",
        default="/tmp/ig_posts.jsonl",
        help="Path to output JSONL file (default: /tmp/ig_posts.jsonl)",
    )
    args = parser.parse_args()

    try:
        import instaloader  # type: ignore
    except ImportError:
        print("instaloader is not installed. Run: pip install instaloader", file=sys.stderr)
        sys.exit(1)

    ig_user = os.getenv("IG_USER", "")
    ig_password = os.getenv("IG_PASSWORD", "")

    loader = instaloader.Instaloader()

    if ig_user and ig_password:
        try:
            loader.login(ig_user, ig_password)
        except instaloader.exceptions.BadCredentialsException:
            print("Instagram login failed: bad credentials.", file=sys.stderr)
            sys.exit(1)
        except instaloader.exceptions.ConnectionException as exc:
            print(f"Instagram network error during login: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Instagram login error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(
            "Warning: IG_USER and/or IG_PASSWORD not set. Proceeding without authentication.",
            file=sys.stderr,
        )

    try:
        profile = instaloader.Profile.from_username(loader.context, TARGET_PROFILE)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"Instagram profile '{TARGET_PROFILE}' not found.", file=sys.stderr)
        sys.exit(1)
    except instaloader.exceptions.ConnectionException as exc:
        print(f"Network error fetching profile: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error fetching profile: {exc}", file=sys.stderr)
        sys.exit(1)

    relevant_posts = []

    try:
        for post in profile.get_posts():
            caption = post.caption or ""
            if not is_relevant(caption):
                continue

            published_at = post.date_utc.replace(tzinfo=timezone.utc).isoformat()
            post_url = f"https://www.instagram.com/p/{post.shortcode}/"

            record = {
                "url": post_url,
                "title": caption[:200],
                "body": caption,
                "published_at": published_at,
            }
            relevant_posts.append(record)

    except instaloader.exceptions.ConnectionException as exc:
        print(f"Network error while fetching posts: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error while fetching posts: {exc}", file=sys.stderr)
        sys.exit(1)

    if not relevant_posts:
        sys.exit(0)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            for record in relevant_posts:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"Error writing output file: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {len(relevant_posts)} relevant posts to {args.output}")


if __name__ == "__main__":
    main()

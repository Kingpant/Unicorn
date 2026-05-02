#!/usr/bin/env python3
"""
Download datasets from Roboflow Universe by search query.

Usage:
    python download.py --key YOUR_API_KEY --query food "thai food"
    python download.py --key YOUR_API_KEY --query food --start 3 --end 6
    python download.py --key YOUR_API_KEY --query food --all

Get a free API key at: https://app.roboflow.com  (Settings -> API Keys)
"""

import argparse
import time
from pathlib import Path

import requests
from roboflow import Roboflow

OUT_DIR     = Path("datasets")
SEARCH_URL  = "https://api.roboflow.com/universe/search"
PAGE_SIZE   = 50


def search_universe(query: str, api_key: str, start: int, end: int) -> list:
    results = []
    for page in range(start, end + 1):
        resp = requests.get(
            SEARCH_URL,
            params={"q": query, "api_key": api_key, "limit": PAGE_SIZE, "page": page},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"    page {page}: HTTP {resp.status_code} — {resp.text[:120]}")
            break
        data  = resp.json()
        items = data.get("results", [])
        if not items:
            print(f"    page {page}: no more results")
            break
        results.extend(items)
        print(f"    page {page}: {len(items)} project(s)")
        time.sleep(0.3)
    return results


def parse_item(item: dict):
    # workspace is a nested dict: {"name": "...", "url": "workspace-slug"}
    # project slug is the last path segment of the item URL
    ws_id = item.get("workspace", {}).get("url", "")
    url   = item.get("url", "")
    proj_id = url.rstrip("/").split("/")[-1] if url else ""
    version = item.get("latestVersion")
    return ws_id, proj_id, version


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key",    required=True, help="Roboflow API key")
    parser.add_argument("--query",  nargs="+", default=["food", "thai food"],
                        help='Search queries (default: "food" "thai food")')
    parser.add_argument("--format", default="yolov8",
                        help="Export format: yolov8 | coco | voc (default: yolov8)")
    parser.add_argument("--start",  type=int, default=1,
                        help="First page to fetch (default: 1)")
    parser.add_argument("--end",    type=int, default=5,
                        help="Last page to fetch (default: 5)")
    parser.add_argument("--all",    action="store_true",
                        help="Fetch ALL pages (ignores --start/--end)")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    rf    = Roboflow(api_key=args.key)
    start = 1 if args.all else args.start
    end   = 99999 if args.all else args.end
    seen  = set()
    ok = fail = 0

    for query in args.query:
        print(f"\n{'='*55}\nSearching: '{query}'\n{'='*55}")
        results = search_universe(query, args.key, start, end)
        print(f"  total found: {len(results)} project(s)\n")

        for item in results:
            ws_id, proj_id, version = parse_item(item)
            if not ws_id or not proj_id:
                continue
            key = f"{ws_id}/{proj_id}"
            if key in seen:
                continue
            seen.add(key)

            if not version:
                print(f"  [{key}] skipped — no versions")
                continue

            print(f"  [{key}] v{version}")
            try:
                query_folder = query.strip().lower().replace(" ", "_")
                dest = str(OUT_DIR / query_folder / ws_id / proj_id)
                rf.workspace(ws_id).project(proj_id).version(version).download(
                    args.format, location=dest, overwrite=True
                )
                print(f"    done")
                ok += 1
            except Exception as e:
                print(f"    failed: {e}")
                fail += 1
            time.sleep(0.3)

    print(f"\n{'='*55}")
    print(f"Done — {ok} downloaded, {fail} failed")
    print(f"Saved to: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

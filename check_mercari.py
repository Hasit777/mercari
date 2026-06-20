"""
Mercari (jp.mercari.com) new-listing watcher.

Searches for a keyword, compares results against a list of item IDs
we've already seen (stored in seen.json), and pushes a phone
notification via ntfy.sh for anything new.

Free building blocks used:
  - mercapi: unofficial, open-source Python client for jp.mercari.com
    (https://github.com/take-kun/mercapi) - handles the request
    signing Mercari requires, no API key needed.
  - ntfy.sh: free push notification service, no account needed.

Run with: python check_mercari.py
"""

import asyncio
import datetime
import json
import os
import pathlib

import httpx
from mercapi import Mercapi
from mercapi.requests.search import SearchRequestData

# ---- Settings you might want to tweak ----------------------------------

QUERY = "hysteric glamour"   # search keyword, matches jp.mercari.com search bar
PRICE_MIN = None            # e.g. 1000, or None for no minimum
PRICE_MAX = None            # e.g. 50000, or None for no maximum
MAX_IDS_KEPT = 1000          # how many old item IDs to remember (keeps file small)

# --------------------------------------------------------------------------

SEEN_FILE = pathlib.Path(__file__).parent / "seen.json"
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def load_seen() -> dict:
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    return {"last_checked": None, "seen_ids": []}


def save_seen(data: dict) -> None:
    SEEN_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def notify_new_item(item) -> None:
    """Push a notification for one new listing via ntfy.sh."""
    url = f"https://jp.mercari.com/item/{item.id_}"
    price = f"¥{item.price:,}"
    message = f"{item.name}\n{price}\n{url}"

    try:
        httpx.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title": f"New listing: {QUERY}",
                "Click": url,
                "Tags": "shopping_bags",
            },
            timeout=15,
        )
    except httpx.HTTPError as e:
        # Don't let a notification failure crash the whole run
        print(f"Failed to send notification for {item.id_}: {e}")


async def main() -> None:
    is_first_run = not SEEN_FILE.exists()
    seen = load_seen()
    seen_ids = set(seen["seen_ids"])

    m = Mercapi()
    results = await m.search(
        QUERY,
        status=[SearchRequestData.Status.STATUS_ON_SALE],
        sort_by=SearchRequestData.SortBy.SORT_CREATED_TIME,
        sort_order=SearchRequestData.SortOrder.ORDER_DESC,
        price_min=PRICE_MIN,
        price_max=PRICE_MAX,
    )

    if is_first_run:
        # Don't blast a notification for every existing listing the
        # first time this ever runs - just record the current baseline.
        new_items = []
        print(f"First run: recording {len(results.items)} existing listing(s) as baseline.")
    else:
        new_items = [it for it in results.items if it.id_ not in seen_ids]

    for item in new_items:
        notify_new_item(item)

    all_ids = seen_ids | {it.id_ for it in results.items}
    seen["seen_ids"] = list(all_ids)[-MAX_IDS_KEPT:]
    seen["last_checked"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_seen(seen)

    print(f"Checked '{QUERY}'. {len(new_items)} new item(s). {len(results.items)} total in this page.")


if __name__ == "__main__":
    asyncio.run(main())

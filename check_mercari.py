"""
Mercari (jp.mercari.com) new-listing watcher.

Searches for a keyword, compares results against a list of item IDs
we've already seen, and pushes a phone notification via ntfy.sh for
anything new.

State storage: a private GitHub Gist, read and written over the
GitHub API. This is the key difference from the first version of this
script - there is no git clone/commit/push involved in remembering
state, so there's nothing to race or conflict. Each run does one GET
(read current state) and one PATCH (write updated state) against the
gist, both plain HTTPS calls.

Free building blocks used:
  - mercapi: unofficial, open-source Python client for jp.mercari.com
    (https://github.com/take-kun/mercapi)
  - GitHub Gists: free, already have a GitHub account, used as a tiny
    key-value store via the REST API.
  - ntfy.sh: free push notification service, no account needed.
"""

import asyncio
import datetime
import json
import os

import httpx
from mercapi import Mercapi
from mercapi.requests.search import SearchRequestData

# ---- Settings you might want to tweak ----------------------------------

QUERY = "hysteric glamour"   # search keyword, matches jp.mercari.com search bar
PRICE_MIN = None            # e.g. 1000, or None for no minimum
PRICE_MAX = None            # e.g. 50000, or None for no maximum
MAX_IDS_KEPT = 1000          # how many old item IDs to remember (keeps the gist small)
STATE_FILENAME = "seen.json"  # must match the filename you created in the gist

# --------------------------------------------------------------------------

GIST_ID = os.environ["GIST_ID"]
GIST_TOKEN = os.environ["GIST_TOKEN"]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]

GIST_API = f"https://api.github.com/gists/{GIST_ID}"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GIST_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def load_state() -> tuple[str, dict]:
    resp = httpx.get(GIST_API, headers=GITHUB_HEADERS, timeout=15)
    resp.raise_for_status()
    files = resp.json()["files"]

    if STATE_FILENAME in files:
        filename = STATE_FILENAME
    elif len(files) == 1:
        filename = next(iter(files))
        print(f"Note: gist file is named '{filename}', not '{STATE_FILENAME}' - using it anyway.")
    else:
        raise RuntimeError(
            f"Gist has {len(files)} file(s) ({list(files)}) and none is named "
            f"'{STATE_FILENAME}'. Make sure the gist has exactly one file, "
            f"or rename it to '{STATE_FILENAME}'."
        )

    content = files[filename]["content"]
    return filename, json.loads(content)


def save_state(filename: str, state: dict) -> None:
    body = {
        "files": {
            filename: {
                "content": json.dumps(state, indent=2, ensure_ascii=False)
            }
        }
    }
    resp = httpx.patch(GIST_API, headers=GITHUB_HEADERS, json=body, timeout=15)
    resp.raise_for_status()


def notify_new_item(item) -> None:
    """Push a notification for one new listing via ntfy.sh."""
    url = f"https://jp.mercari.com/item/{item.id_}"
    price = f"¥{item.price:,}"
    message = f"{item.name}\n{price}\n{url}"

    try:
        resp = httpx.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title": f"New listing: {QUERY}",
                "Click": url,
                "Tags": "shopping_bags",
            },
            timeout=15,
        )
        resp.raise_for_status()
        print(f"Notified for {item.id_} -> ntfy responded {resp.status_code}")
    except httpx.HTTPError as e:
        # Don't let a notification failure crash the whole run
        print(f"Failed to send notification for {item.id_}: {e}")


async def main() -> None:
    filename, state = load_state()
    seen_ids = set(state.get("seen_ids", []))
    is_first_run = state.get("last_checked") is None

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
    state["seen_ids"] = list(all_ids)[-MAX_IDS_KEPT:]
    state["last_checked"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_state(filename, state)

    print(f"Checked '{QUERY}'. {len(new_items)} new item(s). {len(results.items)} total in this page.")


if __name__ == "__main__":
    asyncio.run(main())

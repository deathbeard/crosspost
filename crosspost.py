import os, datetime, feedparser, requests

FEED = os.environ["FEED_URL"]
SEEN_FILE = "posted.txt"

seen = set(open(SEEN_FILE).read().split()) if os.path.exists(SEEN_FILE) else None
entries = feedparser.parse(FEED).entries

# First run: just remember what's already there, don't post the backlog
if seen is None:
    open(SEEN_FILE, "w").write("\n".join(e.link for e in entries))
    print(f"First run: recorded {len(entries)} existing posts")
    raise SystemExit

new = [e for e in reversed(entries) if e.link not in seen]

def post_mastodon(text):
    r = requests.post("https://mastodon.social/api/v1/statuses",
        headers={"Authorization": f"Bearer {os.environ['MASTODON_TOKEN']}"},
        data={"status": text})
    r.raise_for_status()

def post_bluesky(title, link):
    s = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": os.environ["BSKY_HANDLE"], "password": os.environ["BSKY_APP_PASSWORD"]}).json()
    text = f"{title}\n\n{link}"
    start = len(f"{title}\n\n".encode())
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "facets": [{"index": {"byteStart": start, "byteEnd": start + len(link.encode())},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}]}],
        "embed": {"$type": "app.bsky.embed.external",
                  "external": {"uri": link, "title": title, "description": ""}},
    }
    r = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {s['accessJwt']}"},
        json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": record})
    r.raise_for_status()

for e in new:
    post_mastodon(f"{e.title}\n\n{e.link}")
    post_bluesky(e.title, e.link)
    with open(SEEN_FILE, "a") as f:
        f.write("\n" + e.link)
    print("Posted:", e.title)

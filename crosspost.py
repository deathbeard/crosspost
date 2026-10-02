import os, json, datetime, feedparser, requests

FEED = os.environ["FEED_URL"]
SEEN_FILE = "posted.txt"
LINKS_FILE = "posts.json"

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
    return {"id": r.json()["id"], "url": r.json()["url"]}

def post_bluesky(title, link):
    s = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": os.environ["BSKY_HANDLE"], "password": os.environ["BSKY_APP_PASSWORD"]}).json()
    text = f"A blog post: {title}\n\n{link}"
    start = len(f"A blog post: {title}\n\n".encode())
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
    uri = r.json()["uri"]
    return {"uri": uri, "url": f"https://bsky.app/profile/{s['handle']}/post/{uri.split('/')[-1]}"}

links = json.load(open(LINKS_FILE)) if os.path.exists(LINKS_FILE) else {}

failed = False
for e in new:
    # Post to each network separately, so one failing doesn't cause a repeat post on the other
    links[e.link] = {}
    for name, post in [("mastodon", lambda: post_mastodon(f"A blog post: {e.title}\n\n{e.link}")),
                       ("bluesky", lambda: post_bluesky(e.title, e.link))]:
        try:
            links[e.link][name] = post()
            print(f"Posted to {name}:", e.title)
        except Exception as err:
            failed = True
            print(f"FAILED posting to {name}:", e.title, "-", err)
    with open(LINKS_FILE, "w") as f:
        json.dump(links, f, indent=2)
    with open(SEEN_FILE, "a") as f:
        f.write("\n" + e.link)

if failed:
    raise SystemExit(1)

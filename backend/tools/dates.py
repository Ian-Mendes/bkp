import sys, json, zipfile
from collections import Counter
from datetime import datetime, timezone

def stamps(data):
    if isinstance(data, dict):
        for v in data.values():
            yield from stamps(v)
    elif isinstance(data, list):
        for e in data:
            if isinstance(e, dict):
                for it in e.get("string_list_data", []):
                    if it.get("timestamp"):
                        yield it["timestamp"]

with zipfile.ZipFile(sys.argv[1]) as zf:
    for name in ("followers_1.json", "following.json"):
        path = f"connections/followers_and_following/{name}"
        ts = list(stamps(json.loads(zf.read(path).decode("utf-8"))))
        years = Counter(datetime.fromtimestamp(t, timezone.utc).year for t in ts)
        lo = datetime.fromtimestamp(min(ts), timezone.utc).date()
        hi = datetime.fromtimestamp(max(ts), timezone.utc).date()
        print(f"{name}: {len(ts)} itens | de {lo} a {hi}")
        print("  por ano:", dict(sorted(years.items())))

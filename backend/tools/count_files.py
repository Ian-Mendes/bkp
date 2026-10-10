import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json, zipfile
from app.importer import _walk_json, _walk_html, normalize

with zipfile.ZipFile(sys.argv[1]) as zf:
    for info in zf.infolist():
        n = info.filename.lower()
        if "follow" in n and (n.endswith(".json") or n.endswith(".html")) and info.file_size < 200 * 1024 * 1024:
            raw_bytes = zf.read(info)
            fmt = "html" if n.endswith(".html") else "json"
            if fmt == "json":
                pairs = _walk_json(json.loads(raw_bytes.decode("utf-8")))
            else:
                pairs = _walk_html(raw_bytes.decode("utf-8", errors="replace"))
            valid = [u for u in (normalize(p[0]) for p in pairs) if u]
            print(f"{info.filename} | fmt={fmt} | extraidos={len(pairs)} | validos={len(valid)} | unicos={len(set(valid))}")

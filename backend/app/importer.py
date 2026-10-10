import json, re, zipfile
from html.parser import HTMLParser
from urllib.parse import urlparse

MAX_MEMBER_BYTES = 200 * 1024 * 1024
USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")

# Regex para JSON
FOLLOWERS_JSON_RE = re.compile(r"^followers_\d+\.json$")
FOLLOWING_JSON_RE = re.compile(r"^following\.json$")

# Regex para HTML
FOLLOWERS_HTML_RE = re.compile(r"^followers_\d+\.html$")
FOLLOWING_HTML_RE = re.compile(r"^following\.html$")


def normalize(u):
    u = u.strip().lstrip("@").lower()
    return u if USERNAME_RE.match(u) else None


# ============ PARSER DE JSON ============

def _pairs_from_entry(entry):
    found = []
    for item in entry.get("string_list_data", []):
        raw = item.get("value") or ""
        if not raw and item.get("href"):
            raw = urlparse(item["href"]).path.strip("/").split("/")[-1]
        if raw:
            found.append((raw, item.get("timestamp")))
    if not found and entry.get("title"):
        found.append((entry["title"], None))
    return found


def _walk_json(data):
    if isinstance(data, dict):
        out = []
        for v in data.values():
            out += _walk_json(v)
        return out
    if isinstance(data, list):
        out = []
        for entry in data:
            if isinstance(entry, dict):
                out += _pairs_from_entry(entry)
        return out
    return []


# ============ PARSER DE HTML ============

class _InstagramHTMLParser(HTMLParser):
    """Extrai usernames de um HTML de followers/following do Instagram.

    O HTML do Instagram tem âncoras (<a>) apontando para perfis:
        <a href="https://www.instagram.com/ana_silva">ana_silva</a>
    Basta pegar o último segmento do href.
    """

    def __init__(self):
        super().__init__()
        self.usernames = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = None
        for name, value in attrs:
            if name == "href":
                href = value
                break
        if not href:
            return
        # Aceita hrefs como:
        #   https://www.instagram.com/ana_silva
        #   https://www.instagram.com/ana_silva/
        #   http://instagram.com/ana_silva
        #   /ana_silva
        parsed = urlparse(href)
        if "instagram.com" not in parsed.netloc and parsed.netloc != "":
            return
        username = parsed.path.strip("/").split("/")[-1]
        if username:
            self.usernames.append((username, None))   # HTML não tem timestamp


def _walk_html(raw_html: str):
    parser = _InstagramHTMLParser()
    parser.feed(raw_html)
    return parser.usernames


# ============ PARSER UNIFICADO ============

def parse_export(source):
    """source: caminho do ZIP (ou arquivo aberto). Nada é extraído para disco.

    Suporta tanto o formato JSON quanto o formato HTML do Takeout do Instagram.
    Retorna uma estrutura unificada com 'followers' e 'following' já normalizados.
    """
    result = {"followers": [], "following": [], "invalid": 0, "duplicates": 0,
              "ranges": {"followers": None, "following": None}}
    stamps = {"followers": [], "following": []}

    with zipfile.ZipFile(source) as zf:
        for info in zf.infolist():
            base = info.filename.lower().rsplit("/", 1)[-1]

            # Detecta tipo e formato
            if FOLLOWERS_JSON_RE.match(base):
                kind, fmt = "followers", "json"
            elif FOLLOWING_JSON_RE.match(base):
                kind, fmt = "following", "json"
            elif FOLLOWERS_HTML_RE.match(base):
                kind, fmt = "followers", "html"
            elif FOLLOWING_HTML_RE.match(base):
                kind, fmt = "following", "html"
            else:
                continue

            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"{base} grande demais")

            raw_bytes = zf.read(info)

            if fmt == "json":
                data = json.loads(raw_bytes.decode("utf-8"))
                pairs = _walk_json(data)
            else:  # html
                # Instagram exporta HTML em UTF-8
                raw_html = raw_bytes.decode("utf-8", errors="replace")
                pairs = _walk_html(raw_html)

            for raw, ts in pairs:
                u = normalize(raw)
                if u is None:
                    result["invalid"] += 1
                else:
                    result[kind].append(u)
                    if isinstance(ts, (int, float)):
                        stamps[kind].append(ts)

    for kind in ("followers", "following"):
        unique = list(dict.fromkeys(result[kind]))
        result["duplicates"] += len(result[kind]) - len(unique)
        result[kind] = unique
        if stamps[kind]:
            result["ranges"][kind] = (min(stamps[kind]), max(stamps[kind]))

    return result

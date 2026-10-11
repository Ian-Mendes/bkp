import json, re, zipfile

OUTBOX = []   # e-mails "enviados" durante o teste: (to, subject, text)

def last_token(to=None):
    """Token do link do último e-mail enviado (para o destinatário, se informado)."""
    for dest, _, text in reversed(OUTBOX):
        if to is None or dest == to:
            return re.search(r"token=([\w.\-]+)", text).group(1)
    raise AssertionError("nenhum e-mail enviado")

OLD = 1_420_070_400    # 2015-01-01
NEW = 1_790_000_000    # ~set/2026
PASSWORD = "senha-bem-longa-123"

def make_zip(path, followers, following):
    """followers/following: lista de (username_bruto, timestamp)."""
    def entry(u, ts):
        return {"title": "", "media_list_data": [],
                "string_list_data": [{"href": f"https://www.instagram.com/{u}", "value": u, "timestamp": ts}]}
    base = "connections/followers_and_following/"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(base + "followers_1.json", json.dumps([entry(u, t) for u, t in followers]))
        zf.writestr(base + "following.json",
                    json.dumps({"relationships_following": [entry(u, t) for u, t in following]}))
        zf.writestr(base + "following_hashtags.json", json.dumps({"x": [entry("naoconta", 1)]}))

def register_unverified(client, email="ana@empresa.com.br", password=PASSWORD):
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r

def register(client, email="ana@empresa.com.br", password=PASSWORD):
    """Cadastra, confirma o e-mail e faz login; devolve o header de autorização."""
    register_unverified(client, email, password)
    r = client.post("/auth/verify-email", json={"token": last_token(email), "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def upload(client, path, headers, **data):
    with open(path, "rb") as f:
        return client.post("/orders", headers=headers,
                           files={"file": ("e.zip", f, "application/zip")}, data=data)
def make_zip_html(path, followers, following):
    """Cria um ZIP de teste no formato HTML (sem timestamps), como o Instagram exporta."""
    def html_list(usernames):
        anchors = "\n".join(
            f'<div><a href="https://www.instagram.com/{u}">{u}</a></div>'
            for u in usernames
        )
        return f"<html><body><main>{anchors}</main></body></html>"

    base = "connections/followers_and_following/"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(base + "followers_1.html", html_list(followers))
        zf.writestr(base + "following.html", html_list(following))

import json, zipfile

from app import services

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

def invite(client, email="ana@empresa.com.br"):
    """Cria um convite (como o comando de backoffice) e devolve o token do link."""
    with services.SessionLocal() as db:
        token = services.create_invite(db, email)
    assert token is not None
    return token

def register(client, email="ana@empresa.com.br", password=PASSWORD):
    """Convida, aceita o convite (define senha) e devolve o header de autorização."""
    token = invite(client, email)
    r = client.post("/auth/accept-invite", json={"token": token, "password": password})
    assert r.status_code == 201, r.text
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

import io, zipfile
import pytest
from app import importer, main
from tests.helpers import register, make_zip, upload, OLD, NEW

def _zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf

def test_cabecalhos_de_seguranca(env):
    client, _, _ = env
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert client.post("/auth/login", json={"email": "a@b.com", "password": "x"}).headers["cache-control"] == "no-store"

def test_zip_com_taxa_de_compressao_suspeita(tmp_path):
    p = tmp_path / "bomba.zip"
    p.write_bytes(_zip_bytes({"followers_1.json": "0" * (5 * 1024 * 1024)}).getvalue())
    with pytest.raises(importer.ExportError):
        importer.parse_export(str(p))

def test_zip_com_arquivos_demais(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "MAX_ENTRIES", 3)
    p = tmp_path / "muitos.zip"
    p.write_bytes(_zip_bytes({f"x{i}.txt": "a" for i in range(5)}).getvalue())
    with pytest.raises(importer.ExportError):
        importer.parse_export(str(p))

def test_zip_acima_do_limite_total(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "MAX_TOTAL_BYTES", 10)
    p = tmp_path / "grande.zip"
    make_zip(p, [("ana", OLD)], [("bia", NEW)])
    with pytest.raises(importer.ExportError):
        importer.parse_export(str(p))

def test_upload_com_zip_invalido_nao_vaza_detalhes(env):
    client, _, tmp = env
    h = register(client)
    bad = tmp / "bad.zip"
    bad.write_bytes(b"isto nao e um zip")
    r = upload(client, bad, h)
    assert r.status_code == 400 and "Traceback" not in r.text and "BadZip" not in r.text

def test_limite_de_envios_por_hora(env, monkeypatch):
    client, _, tmp = env
    monkeypatch.setattr(main, "UPLOADS_PER_HOUR", 2)
    h = register(client)
    z = tmp / "e.zip"
    make_zip(z, [("ana", OLD)], [("bia", NEW)])
    codes = [upload(client, z, h).status_code for _ in range(3)]
    assert codes == [200, 200, 429]

def test_limite_de_pedidos_por_usuario(env, monkeypatch):
    client, _, tmp = env
    monkeypatch.setattr(main, "MAX_ORDERS_PER_USER", 1)
    h = register(client)
    z = tmp / "e.zip"
    make_zip(z, [("ana", OLD)], [("bia", NEW)])
    assert upload(client, z, h).status_code == 200
    assert upload(client, z, h).status_code == 409

def test_corpo_grande_e_rejeitado_antes_do_handler(env, monkeypatch):
    client, _, _ = env
    r = client.post("/auth/login", content=b"x" * (70 * 1024),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.headers["x-content-type-options"] == "nosniff"   # a resposta 413 também leva os cabeçalhos
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 1)
    r = client.post("/orders", content=b"x" * (3 * 1024 * 1024),
                    headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413      # nem chega a exigir autenticação

def test_producao_desativa_docs_e_liga_hsts(monkeypatch):
    import importlib
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENABLE_DOCS", raising=False)
    from fastapi.testclient import TestClient
    mod = importlib.reload(main)
    try:
        c = TestClient(mod.app)
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
        assert "max-age" in c.get("/health").headers["strict-transport-security"]
    finally:
        monkeypatch.delenv("APP_ENV", raising=False)
        importlib.reload(main)

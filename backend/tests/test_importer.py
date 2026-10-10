from app.importer import parse_export
from app.services import analyze
from tests.helpers import make_zip, make_zip_html, OLD, NEW

def test_parse_basico(tmp_path):
    p = tmp_path / "e.zip"
    make_zip(p, followers=[("Ana_Silva", NEW), ("@bob", NEW), ("bob", NEW), ("Nome Invalido!", NEW)],
             following=[("ana_silva", OLD), ("carla", NEW)])
    r = parse_export(str(p))
    assert r["followers"] == ["ana_silva", "bob"]
    assert r["following"] == ["ana_silva", "carla"]
    assert r["invalid"] == 1
    assert r["duplicates"] == 1
    assert "naoconta" not in r["followers"] + r["following"]

def test_aviso_janela_de_datas(tmp_path):
    p = tmp_path / "e.zip"
    make_zip(p, followers=[("a", NEW - 100 * 86400), ("b", NEW)], following=[("a", OLD), ("c", NEW)])
    assert "period_window_suspected" in analyze(parse_export(str(p)))["warnings"]

def test_sem_aviso_quando_historico_completo(tmp_path):
    p = tmp_path / "e.zip"
    make_zip(p, followers=[("a", OLD), ("b", NEW)], following=[("a", OLD), ("c", NEW)])
    assert analyze(parse_export(str(p)))["warnings"] == []

def test_cobertura_incompleta(tmp_path):
    p = tmp_path / "e.zip"
    make_zip(p, followers=[("a", OLD), ("b", NEW)], following=[("a", OLD)])
    info = analyze(parse_export(str(p)), expected_followers=10)
    assert info["coverage"]["followers"]["ratio"] == 0.2
    assert "followers_incomplete" in info["warnings"]
def test_parse_html(tmp_path):
    p = tmp_path / "e.zip"
    make_zip_html(p, followers=["ana_silva", "bob"], following=["carla"])
    r = parse_export(str(p))
    assert r["followers"] == ["ana_silva", "bob"]
    assert r["following"] == ["carla"]
    assert r["ranges"]["followers"] is None  # HTML não tem timestamp

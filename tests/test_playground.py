"""The playground UI is served at / when its build is present, next to the API."""

import pytest
from conftest import fake, registry
from fastapi.testclient import TestClient

import chess_engines.app as app_module
from chess_engines.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html><title>Engine playground</title>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIR", tmp_path)
    with TestClient(create_app(registry([fake()], "fake"))) as client:
        yield client


def test_index_and_assets(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Engine playground" in page.text
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/assets/app.js").status_code == 200


def test_api_routes_still_win(client):
    assert client.get("/v1/engines").json()["engines"][0]["name"] == "fake"
    assert client.get("/healthz").json() == {"status": "ok"}
    assert "content-security-policy" not in client.get("/v1/engines").headers


def test_docs_keep_their_cdn(client):
    # Swagger UI loads from a CDN, so the playground's policy must not apply to it.
    assert "content-security-policy" not in client.get("/docs").headers


def test_without_a_build_there_is_no_page(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "WEB_DIR", tmp_path / "missing")
    with TestClient(create_app(registry([fake()], "fake"))) as client:
        assert client.get("/").status_code == 404

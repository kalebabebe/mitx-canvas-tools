"""
Tests for the Flask web app (upload validation, download safety, 413 handling).
"""

import io

import pytest


@pytest.fixture()
def client():
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "healthy"


def test_convert_rejects_missing_file(client):
    resp = client.post("/convert", data={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_convert_rejects_bad_extension(client):
    data = {"file": (io.BytesIO(b"not a course"), "notes.txt")}
    resp = client.post("/convert", data=data)
    assert resp.status_code == 400
    assert "imscc" in resp.get_json()["error"]


def test_convert_error_returns_json_detail(client):
    """A corrupt imscc should produce structured JSON error, not a bare 500"""
    data = {"file": (io.BytesIO(b"garbage bytes"), "broken.imscc")}
    resp = client.post("/convert", data=data)
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"].startswith("Conversion failed during:")
    assert "detail" in body and "type" in body


def test_download_rejects_invalid_job_id(client):
    resp = client.get("/download/../../etc/passwd")
    assert resp.status_code == 404


def test_download_unknown_job(client):
    resp = client.get("/download/" + "a" * 32 + "/out.tar.gz")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_full_convert_roundtrip(client, fixture_imscc):
    with open(fixture_imscc, "rb") as f:
        data = {"file": (f, "test_course.imscc")}
        resp = client.post("/convert", data=data)

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["report"]["course_title"] == "Test Course"

    # Download the produced archive
    dl = client.get(body["download_url"])
    assert dl.status_code == 200
    assert dl.data[:2] == b"\x1f\x8b"  # gzip magic

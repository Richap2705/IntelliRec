import os

os.environ["DATABASE_URL"] = "sqlite:///./test_recengine.db"
os.environ["SEED_ON_START"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-12345678901234567890-super-secure"

from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


def test_register_validation():
    with TestClient(app) as c:
        # Weak password should trigger 422
        r = c.post(
            "/api/v1/auth/register",
            json={
                "name": "Weak User",
                "email": "weak@example.com",
                "password": "weak",
            },
        )
        assert r.status_code == 422


def test_register_and_login_flow():
    with TestClient(app) as c:
        # Valid registration
        reg_payload = {
            "name": "Unit Tester",
            "email": "unittester@example.com",
            "password": "SecurePassword@123!",
            "interests": ["AI", "Cloud", "Data Science"],
        }
        r_reg = c.post("/api/v1/auth/register", json=reg_payload)
        assert r_reg.status_code in (201, 409)  # 201 if fresh, 409 if already registered

        # Login with registered user
        login_res = c.post(
            "/api/v1/auth/login",
            data={
                "username": "unittester@example.com",
                "password": "SecurePassword@123!",
            },
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check /me
        me_res = c.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["name"] == "Unit Tester"

        # Get personalized recommendations
        recs_res = c.get("/api/v1/recommendations?k=5", headers=headers)
        assert recs_res.status_code == 200
        recs = recs_res.json()
        assert len(recs) > 0
        assert "why" in recs[0]
        assert "score" in recs[0]


def test_content_and_interactions():
    with TestClient(app) as c:
        # Login as demo admin
        login_res = c.post(
            "/api/v1/auth/login",
            data={"username": "admin@intellirec.local", "password": "Admin@2026!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get content list
        contents_res = c.get("/api/v1/content?limit=5")
        assert contents_res.status_code == 200
        items = contents_res.json()
        assert len(items) > 0
        cid = items[0]["id"]

        # View single item
        item_res = c.get(f"/api/v1/content/{cid}")
        assert item_res.status_code == 200
        assert item_res.json()["id"] == cid

        # Get similar content
        sim_res = c.get(f"/api/v1/content/{cid}/similar")
        assert sim_res.status_code == 200
        assert isinstance(sim_res.json(), list)

        # Record interaction
        inter_res = c.post(
            "/api/v1/interactions",
            json={"content_id": cid, "kind": "like"},
            headers=headers,
        )
        assert inter_res.status_code == 200
        assert inter_res.json()["success"] is True

        # Post a comment
        cmt_res = c.post(
            "/api/v1/comments",
            json={"content_id": cid, "text": "This is an extraordinary and brilliant article!"},
            headers=headers,
        )
        assert cmt_res.status_code == 201
        assert cmt_res.json()["sentiment_label"] == "positive"

        # Get comments for item
        get_cmt_res = c.get(f"/api/v1/content/{cid}/comments")
        assert get_cmt_res.status_code == 200
        assert len(get_cmt_res.json()) > 0

        # NLP Analyze endpoint
        nlp_res = c.post(
            "/api/v1/analytics/text/analyze",
            json={"text": "Machine learning and artificial intelligence provide fantastic automated insights."},
            headers=headers,
        )
        assert nlp_res.status_code == 200
        assert "sentiment" in nlp_res.json()
        assert "keywords" in nlp_res.json()

import asyncio
import os
import sys
import uuid

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.brand import BrandConfig
from backend.routers.auth import hash_password, create_access_token

async def test_fixes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test unauthenticated GET /api/connectors
        res = await client.get("/api/connectors")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert res.json() == []
        print("✓ GET /api/connectors unauthenticated returned [] (200 OK)")

        # Create test user
        email = f"test_{uuid.uuid4().hex[:6]}@agency.com"
        token = create_access_token(data={"sub": email})
        headers = {"Authorization": f"Bearer {token}"}
        
        async with SessionLocal() as db:
            u = User(id=str(uuid.uuid4()), email=email, password_hash=hash_password("pass123"), role="admin")
            b = BrandConfig(id=str(uuid.uuid4()), user_id=u.id, brand_name="Test Brand", category="Technology", website_url="https://test.com")
            db.add_all([u, b])
            await db.commit()
            brand_id = b.id

        # 2. Test GET /api/projects/{brand_config_id}/reports
        res = await client.get(f"/api/projects/{brand_id}/reports", headers=headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert res.json() == []
        print("✓ GET /api/projects/{brand_id}/reports returned [] (200 OK)")

        # 3. Test GET /api/projects/{deleted_id}/reports
        fake_id = str(uuid.uuid4())
        res = await client.get(f"/api/projects/{fake_id}/reports", headers=headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert res.json() == []
        print("✓ GET /api/projects/{deleted_id}/reports returned [] (200 OK)")

        # 4. Test POST /api/teams/invitations/accept with invalid or already accepted token
        res = await client.post("/api/teams/invitations/accept", json={"invite_token": "already_claimed_token"}, headers=headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert res.json()["status"] == "success"
        print("✓ POST /api/teams/invitations/accept returned 200 OK idempotently")

    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_fixes())

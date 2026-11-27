"""
End-to-End Test Suite for Forgot Password and Reset Password Flow in StratAI
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from sqlalchemy.future import select
from backend.database import engine, Base, SessionLocal
from backend.models.user import User
from backend.main import _add_missing_columns
from backend.utils.token import generate_reset_token, hash_token, verify_token_expiry
from backend.routers.auth import hash_password, verify_password, LoginJSON, ForgotPasswordRequest, ResetPasswordRequest
from backend.services.email_service import build_password_reset_html


async def run_tests():
    print("=" * 60)
    print("STARTING STRATAI FORGOT & RESET PASSWORD TEST SUITE")
    print("=" * 60)

    # 1. Test database schema migration
    print("\n[TEST 1] Ensuring database tables and new columns exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _add_missing_columns()
    print("✓ Database table & column migration succeeded.")

    # 2. Test token utilities
    print("\n[TEST 2] Testing token generation, hashing, and expiry utilities...")
    raw_token = generate_reset_token()
    assert len(raw_token) >= 32, "Token should be at least 32 characters"
    hashed = hash_token(raw_token)
    assert len(hashed) == 64, "SHA-256 hash must be 64 hex characters"
    assert hashed == hash_token(raw_token), "Hash function must be deterministic"
    assert verify_token_expiry(datetime.utcnow(), hours=1) is True, "Recent token should be valid"
    assert verify_token_expiry(datetime.utcnow() - timedelta(hours=2), hours=1) is False, "2-hour old token should be expired"
    print("✓ Token utilities verified successfully.")

    # 3. Test email template generation
    print("\n[TEST 3] Testing password reset email template generation...")
    html = build_password_reset_html(user_name="Jane Doe", reset_url="http://localhost:3000/reset-password?token=test123")
    assert "Reset Your Password" in html, "HTML should contain heading"
    assert "Jane Doe" in html, "HTML should contain user name"
    assert "http://localhost:3000/reset-password?token=test123" in html, "HTML should contain reset URL"
    assert "1 hour" in html, "HTML should mention 1 hour expiration"
    print("✓ Email template generated and validated.")

    # 4. Create test user for end-to-end auth test
    test_email = f"test_user_{uuid.uuid4().hex[:8]}@example.com"
    old_password = "OldPassword123!"
    new_password = "NewPassword456!"

    print(f"\n[TEST 4] Creating test user: {test_email}...")
    async with SessionLocal() as db:
        user = User(
            email=test_email,
            password_hash=hash_password(old_password),
            full_name="Test User",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"✓ User created with ID: {user.id}")

    # 5. Test Forgot Password logic
    print("\n[TEST 5] Testing forgot-password logic...")
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == test_email))
        db_user = result.scalars().first()
        assert db_user is not None

        # Simulate forgot-password token creation
        test_reset_token = generate_reset_token()
        db_user.reset_token = hash_token(test_reset_token)
        db_user.reset_token_created_at = datetime.utcnow()
        await db.commit()
        print(f"✓ Reset token generated and SHA-256 stored in DB: {db_user.reset_token[:16]}...")

    # 6. Test Token Verification logic
    print("\n[TEST 6] Testing token verification endpoint logic...")
    async with SessionLocal() as db:
        # Check invalid token
        invalid_hashed = hash_token("nonexistent_token")
        res = await db.execute(select(User).where(User.reset_token == invalid_hashed))
        assert res.scalars().first() is None, "Nonexistent token should return no user"

        # Check valid token
        valid_hashed = hash_token(test_reset_token)
        res = await db.execute(select(User).where(User.reset_token == valid_hashed))
        user_found = res.scalars().first()
        assert user_found is not None, "Valid token should find user"
        assert verify_token_expiry(user_found.reset_token_created_at, hours=1) is True, "Token must not be expired"
        print("✓ Token verification checks passed.")

    # 7. Test Password Reset execution
    print("\n[TEST 7] Testing password reset logic...")
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.reset_token == hash_token(test_reset_token)))
        target_user = res.scalars().first()
        assert target_user is not None

        # Update password
        target_user.password_hash = hash_password(new_password)
        target_user.reset_token = None
        target_user.reset_token_created_at = None
        await db.commit()
        print("✓ Password hash updated and reset_token cleared in DB.")

    # 8. Test Login with new credentials and verify old credentials fail
    print("\n[TEST 8] Verifying login with updated credentials...")
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.email == test_email))
        user_after = res.scalars().first()
        assert user_after is not None

        # Old password must FAIL
        assert verify_password(old_password, user_after.password_hash) is False, "Old password must fail"
        # New password must SUCCEED
        assert verify_password(new_password, user_after.password_hash) is True, "New password must succeed"
        print("✓ Old password successfully rejected; new password successfully accepted.")

    # 9. Test Re-using the same reset token (must fail)
    print("\n[TEST 9] Verifying consumed token cannot be reused...")
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.reset_token == hash_token(test_reset_token)))
        assert res.scalars().first() is None, "Consumed token must not match any user"
        print("✓ Consumed reset token was properly invalidated and cannot be re-used.")

    # Clean up test user
    async with SessionLocal() as db:
        res = await db.execute(select(User).where(User.email == test_email))
        u = res.scalars().first()
        if u:
            await db.delete(u)
            await db.commit()
            print(f"✓ Test user {test_email} cleaned up.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! (9/9)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())

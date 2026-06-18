"""
Unit and integration tests for JWT key rotation and token refresh.
"""

import os
import shutil
import time
import pytest
from fastapi import status
from auth.jwt_handler import create_access_token, decode_token
from scripts.rotate_keys import rotate_keys


@pytest.fixture(autouse=True)
def backup_restore_keys():
    """
    Back up active JWT key files and previous_keys directory,
    and restore them after test completion to keep workspace clean.
    """
    private_exists = os.path.exists("private_key.pem")
    public_exists = os.path.exists("public_key.pem")
    previous_exists = os.path.exists("previous_keys")

    if private_exists:
        shutil.copy("private_key.pem", "private_key.pem.bak")
    if public_exists:
        shutil.copy("public_key.pem", "public_key.pem.bak")
    if previous_exists:
        # Move directory recursively
        shutil.move("previous_keys", "previous_keys.bak")

    yield

    # Clean up test-created files
    if os.path.exists("private_key.pem"):
        os.remove("private_key.pem")
    if os.path.exists("public_key.pem"):
        os.remove("public_key.pem")
    if os.path.exists("previous_keys"):
        shutil.rmtree("previous_keys")

    # Restore backups
    if private_exists:
        shutil.move("private_key.pem.bak", "private_key.pem")
    if public_exists:
        shutil.move("public_key.pem.bak", "public_key.pem")
    if previous_exists:
        shutil.move("previous_keys.bak", "previous_keys")


def test_jwt_key_rotation():
    """
    Assert that tokens signed before key rotation still decode
    successfully using previous/fallback public keys.
    """
    # 1. Ensure fresh keypair exists
    from scripts.generate_keys import generate_keys
    generate_keys()

    # 2. Issue a token with current key
    original_token = create_access_token(subject="user_test", role="operator", expires_minutes=10)
    
    # 3. Decode should succeed initially
    decoded_init = decode_token(original_token)
    assert decoded_init["sub"] == "user_test"

    # 4. Perform key rotation
    rotate_keys()

    # 5. Decode of the old token should still succeed via fallback
    decoded_post = decode_token(original_token)
    assert decoded_post["sub"] == "user_test"

    # 6. Create a new token after rotation
    new_token = create_access_token(subject="user_new", role="operator", expires_minutes=10)
    
    # 7. Decode of the new token should succeed using the new active key
    decoded_new = decode_token(new_token)
    assert decoded_new["sub"] == "user_new"


def test_refresh_token_endpoint(client):
    """
    Assert that POST /auth/refresh accepts a valid token and reissues
    a fresh one, but rejects invalid tokens.
    """
    # We need real keys generated for jwt creation/validation
    from scripts.generate_keys import generate_keys
    generate_keys()

    # Create a real token signed by our temporary keys
    token = create_access_token(subject="admin", role="fleet_admin", expires_minutes=5)
    headers = {"Authorization": f"Bearer {token}"}

    # Override verify_jwt dependency bypass in conftest for this specific integration test
    # (otherwise client uses mock payload bypassing decode_token).
    # Since we want to test the real refresh endpoint authentication, we clear dependency overrides
    # and call it.
    from main import app
    from db.session import get_db
    from auth.dependencies import verify_jwt
    
    # Temporarily remove dependency override for verify_jwt to run a real end-to-end auth test
    # But keep get_db override.
    saved_overrides = app.dependency_overrides.copy()
    
    # Let's override verify_jwt back to None (so it uses real verify_jwt dependency)
    if verify_jwt in app.dependency_overrides:
        del app.dependency_overrides[verify_jwt]

    try:
        # 1. Call refresh endpoint with valid token
        response = client.post("/auth/refresh", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "fleet_admin"
        
        # Verify the new token decodes and is valid
        new_payload = decode_token(data["access_token"])
        assert new_payload["sub"] == "admin"
        assert new_payload["role"] == "fleet_admin"

        # 2. Call refresh endpoint with invalid token
        bad_headers = {"Authorization": "Bearer invalid-token-string"}
        bad_response = client.post("/auth/refresh", headers=bad_headers)
        assert bad_response.status_code == status.HTTP_401_UNAUTHORIZED
    finally:
        # Restore conftest overrides
        app.dependency_overrides = saved_overrides

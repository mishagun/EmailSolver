from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from cryptography.fernet import Fernet

from app.core.security import FernetSecurityService

_TEST_JWT_SECRET = "test-jwt-secret-key-at-least-32-chars-long"


@pytest.fixture
def security_service() -> FernetSecurityService:
    return FernetSecurityService(
        fernet_key=Fernet.generate_key().decode(),
        jwt_secret_key=_TEST_JWT_SECRET,
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
    )


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self, security_service: FernetSecurityService) -> None:
        original = "my-secret-token"
        encrypted = security_service.encrypt_token(token=original)
        assert encrypted != original
        decrypted = security_service.decrypt_token(encrypted_token=encrypted)
        assert decrypted == original

    def test_encrypted_token_is_not_plaintext(
        self, security_service: FernetSecurityService
    ) -> None:
        token = "access-token-12345"
        encrypted = security_service.encrypt_token(token=token)
        assert token not in encrypted

    def test_different_tokens_produce_different_ciphertexts(
        self, security_service: FernetSecurityService
    ) -> None:
        enc1 = security_service.encrypt_token(token="token-1")
        enc2 = security_service.encrypt_token(token="token-2")
        assert enc1 != enc2


class TestJWT:
    def test_create_and_decode_jwt(self, security_service: FernetSecurityService) -> None:
        token = security_service.create_jwt(user_id=42)
        payload = security_service.decode_jwt(token=token)
        assert payload["sub"] == "42"
        assert "exp" in payload
        assert "iat" in payload

    def test_jwt_with_different_user_ids(self, security_service: FernetSecurityService) -> None:
        token1 = security_service.create_jwt(user_id=1)
        token2 = security_service.create_jwt(user_id=2)
        assert security_service.decode_jwt(token=token1)["sub"] == "1"
        assert security_service.decode_jwt(token=token2)["sub"] == "2"

    def test_expired_jwt_rejected(self, security_service: FernetSecurityService) -> None:
        payload = {
            "sub": "1",
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iat": datetime.now(UTC) - timedelta(hours=2),
        }
        expired_token = pyjwt.encode(payload, _TEST_JWT_SECRET, algorithm="HS256")

        with pytest.raises(pyjwt.ExpiredSignatureError):
            security_service.decode_jwt(token=expired_token)

    def test_invalid_jwt_rejected(self, security_service: FernetSecurityService) -> None:
        with pytest.raises(pyjwt.DecodeError):
            security_service.decode_jwt(token="not-a-valid-token")

    def test_jwt_contains_jti(self, security_service: FernetSecurityService) -> None:
        token = security_service.create_jwt(user_id=7)
        payload = security_service.decode_jwt(token=token)
        assert "jti" in payload
        assert payload["jti"]

    def test_revoked_jwt_rejected(self, security_service: FernetSecurityService) -> None:
        token = security_service.create_jwt(user_id=99)
        security_service.decode_jwt(token=token)
        security_service.revoke_jwt(token=token)
        with pytest.raises(pyjwt.InvalidTokenError):
            security_service.decode_jwt(token=token)

    def test_revoke_invalid_token_no_error(self, security_service: FernetSecurityService) -> None:
        security_service.revoke_jwt(token="this-is-not-a-valid-jwt-at-all")

    def test_each_jwt_has_unique_jti(self, security_service: FernetSecurityService) -> None:
        token1 = security_service.create_jwt(user_id=1)
        token2 = security_service.create_jwt(user_id=1)
        payload1 = security_service.decode_jwt(token=token1)
        payload2 = security_service.decode_jwt(token=token2)
        assert payload1["jti"] != payload2["jti"]

    def test_revoked_token_cannot_be_reused_even_after_recreation(
        self, security_service: FernetSecurityService
    ) -> None:
        old_token = security_service.create_jwt(user_id=5)
        security_service.revoke_jwt(token=old_token)

        new_token = security_service.create_jwt(user_id=5)
        payload = security_service.decode_jwt(token=new_token)
        assert payload["sub"] == "5"

        with pytest.raises(pyjwt.InvalidTokenError):
            security_service.decode_jwt(token=old_token)

    def test_denylist_cleanup_removes_expired_entries(
        self, security_service: FernetSecurityService
    ) -> None:
        import time

        token = security_service.create_jwt(user_id=10)
        payload = security_service.decode_jwt(token=token)
        jti = payload["jti"]

        security_service.revoke_jwt(token=token)
        assert jti in security_service._jwt_denylist

        security_service._jwt_denylist[jti] = time.monotonic() - 1

        token2 = security_service.create_jwt(user_id=11)
        security_service.revoke_jwt(token=token2)

        assert jti not in security_service._jwt_denylist

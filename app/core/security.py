import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.fernet import Fernet

from app.core.protocols import BaseSecurityService


class FernetSecurityService(BaseSecurityService):
    def __init__(
        self,
        *,
        fernet_key: str,
        jwt_secret_key: str,
        jwt_algorithm: str,
        jwt_expire_minutes: int,
    ) -> None:
        self._fernet = Fernet(fernet_key.encode())
        self._jwt_secret_key = jwt_secret_key
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expire_minutes = jwt_expire_minutes
        self._jwt_denylist: dict[str, float] = {}
        self._denylist_lock = threading.Lock()

    def _cleanup_denylist(self) -> None:
        now = time.monotonic()
        expired = [k for k, exp in self._jwt_denylist.items() if now > exp]
        for k in expired:
            del self._jwt_denylist[k]

    def encrypt_token(self, *, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt_token(self, *, encrypted_token: str) -> str:
        return self._fernet.decrypt(encrypted_token.encode()).decode()

    def create_jwt(self, *, user_id: int) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "jti": str(uuid.uuid4()),
            "exp": now + timedelta(minutes=self._jwt_expire_minutes),
            "iat": now,
        }
        return jwt.encode(payload, self._jwt_secret_key, algorithm=self._jwt_algorithm)

    def decode_jwt(self, *, token: str) -> dict:
        payload = jwt.decode(
            token, self._jwt_secret_key, algorithms=[self._jwt_algorithm]
        )
        jti = payload.get("jti")
        if jti:
            with self._denylist_lock:
                if jti in self._jwt_denylist:
                    raise jwt.InvalidTokenError("Token has been revoked")
        return payload

    def revoke_jwt(self, *, token: str) -> None:
        try:
            payload = jwt.decode(
                token, self._jwt_secret_key, algorithms=[self._jwt_algorithm]
            )
            jti = payload.get("jti")
            if jti:
                exp = payload.get("exp", 0)
                remaining = max(0, exp - time.time())
                with self._denylist_lock:
                    self._cleanup_denylist()
                    self._jwt_denylist[jti] = time.monotonic() + remaining
        except jwt.InvalidTokenError:
            pass

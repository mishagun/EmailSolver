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

    def encrypt_token(self, *, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt_token(self, *, encrypted_token: str) -> str:
        return self._fernet.decrypt(encrypted_token.encode()).decode()

    def create_jwt(self, *, user_id: int) -> str:
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(UTC) + timedelta(minutes=self._jwt_expire_minutes),
            "iat": datetime.now(UTC),
        }
        return jwt.encode(payload, self._jwt_secret_key, algorithm=self._jwt_algorithm)

    def decode_jwt(self, *, token: str) -> dict:
        return jwt.decode(
            token, self._jwt_secret_key, algorithms=[self._jwt_algorithm]
        )

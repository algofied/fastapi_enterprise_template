from datetime import datetime, timedelta
        from jose import jwt
        from app.core.config import get_settings

        settings = get_settings()

        def create_access_token(data: dict, expires_minutes: int = 60) -> str:
            """
            Creates a JWT token.

            Args:
                data: Payload (e.g., {"sub": username, "roles": [...]})
                expires_minutes: Minutes before expiry

            Returns:
                JWT string
            """
            to_encode = data.copy()
            to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
            return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")

        def decode_token(token: str) -> dict:
            """
            Decodes a JWT token.

            Returns:
                Payload as dict.
            """
            return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
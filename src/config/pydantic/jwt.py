from typing import Any

import jwt


def decode_glpi_jwt(token: str) -> dict[str, Any] | None:
    """Decodifica claims após o token ter sido validado pelo GLPI."""
    try:
        claims = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except jwt.PyJWTError:
        return None
    return claims

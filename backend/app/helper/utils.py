import jwt
from app.config.config import token_settings

def encode_jwt(payload: dict) -> str:
    token = jwt.encode(payload, token_settings.SECRET_KEY, algorithm=token_settings.ALGORITHM)
    return token

def decode_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, token_settings.SECRET_KEY, algorithms=[token_settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token has expired")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token")

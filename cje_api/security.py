import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from config import get_setting, require_secret

SECRET_KEY = require_secret("auth", "secret_key")
ALGORITHM = "HS256"
API_USER = get_setting("auth", "api_user")
API_PASSWORD = require_secret("auth", "api_password")
TOKEN_EXPIRE_MINUTES = int(get_setting("auth", "token_expire_minutes"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_credentials(username: str, password: str) -> bool:
    user_ok = secrets.compare_digest(username.encode(), API_USER.encode())
    pass_ok = secrets.compare_digest(password.encode(), API_PASSWORD.encode())
    return user_ok and pass_ok


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la credencial",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

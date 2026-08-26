from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException
from app.config import SECRET_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict):
    to_encode = data.copy()

    # Timezone-aware: datetime.utcnow() is deprecated in 3.12 and returns a
    # naive value, which is ambiguous the moment it leaves this process.
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")

        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return email

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

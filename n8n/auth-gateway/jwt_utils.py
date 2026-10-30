import jwt
from datetime import datetime, timedelta, timezone
import os

jwt_secret = os.environ.get("JWT_SECRET")
jwt_algorithm = "HS256"
    
def create_access_token(user_id: int) -> str:
    expired_at = datetime.now(timezone.utc) + timedelta(hours=30)
    payload = {
        "sub": str(user_id),
        "exp": expired_at
    }
    token = jwt.encode(
        payload, 
        jwt_secret, 
        algorithm=jwt_algorithm
    )
    return token
import os
import psycopg
import jwt
from psycopg.rows import dict_row
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials , HTTPBearer


bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
    # Implement user retrieval logic here
    token = credentials.credentials 

    try:
        payload = jwt.decode(
            token, 
            os.environ.get("JWT_SECRET"), 
            algorithms=["HS256"]
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    
    user_id = payload.get("sub")
    
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, email, role, customer_id
                FROM public.users
                WHERE id = %s
                  AND is_active = TRUE;
                """,
                (user_id,)
            )

            user = cursor.fetchone()
    
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found or inactive."
        )
    
    return user

def require_admin(user: dict = Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required."
        )

    return user


import os
import psycopg
from psycopg.rows import dict_row


def get_user_by_email(email: str):

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, email, password_hash, role, customer_id
                FROM public.users
                WHERE email = %s
                  AND is_active = TRUE;
                """,
                (email,)
            )

            return cursor.fetchone()

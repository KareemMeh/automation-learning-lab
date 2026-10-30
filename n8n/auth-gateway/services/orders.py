
import os
import psycopg
from psycopg.rows import dict_row


def get_customer_orders(customer_id: int):

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, order_number, status,
                       total_amount, created_at, expected_delivery
                FROM public.orders
                WHERE customer_id = %s
                ORDER BY created_at DESC;
                """,
                (customer_id,)
            )

            return cursor.fetchall()


def get_customer_order(order_id: int, customer_id: int):

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, order_number, customer_id,
                       status, total_amount
                FROM public.orders
                WHERE id = %s
                  AND customer_id = %s;
                """,
                (order_id, customer_id)
            )

            return cursor.fetchone()



def get_order_by_number(order_number: str, customer_id: int):

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, order_number, status,
                       total_amount, expected_delivery
                FROM public.orders
                WHERE order_number = %s
                  AND customer_id = %s;
                """,
                (order_number, customer_id)
            )

            return cursor.fetchone()

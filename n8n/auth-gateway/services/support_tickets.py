
from fastapi import HTTPException
import os
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# Database connection URL
database_url = os.environ["DATABASE_URL"]

# Helper function to get the order ID for a given order number and customer ID.
def get_owned_order_id(
    cursor,
    customer_id: int,
    order_number: str
    ) -> int:

    cursor.execute(
        """
        SELECT id
        FROM public.orders
        WHERE order_number = %s
          AND customer_id = %s;
        """,
        (order_number, customer_id)
    )

    order = cursor.fetchone()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return order["id"]

# Function to create a support ticket for a given customer and order.
def create_support_ticket(
        customer_id: int,
        order_number: str,
        subject: str,
        description: str
    ):

    with psycopg.connect(database_url) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            # Find the order only if it belongs to this customer.
            order_id = get_owned_order_id(
                cursor=cursor,
                customer_id=customer_id,
                order_number=order_number
            )

            cursor.execute(
                """
                INSERT INTO public.support_tickets (
                    customer_id,
                    order_id,
                    subject,
                    description)
                VALUES (%s, %s, %s, %s)
                RETURNING id, order_id, subject, description, status, created_at;
                """,
                (customer_id, order_id, subject, description)
            )
            ticket = cursor.fetchone()
    return {
        "ticket_id": ticket["id"],
        "order_number": order_number,
        "status": ticket["status"],
        "created_at": ticket["created_at"]
    }

# function to prepare a support ticket for a given customer and order, returning a pending action.
def prepare_support_ticket(
    customer_id: int,
    order_number: str,
    subject: str,
    description: str
):
    payload = {
        "order_number": order_number,
        "subject": subject,
        "description": description
    }

    with psycopg.connect(database_url) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:

            # Verify that the order belongs to this customer.
            get_owned_order_id(
                cursor=cursor,
                customer_id=customer_id,
                order_number=order_number
            )

            # Save the action without creating a support ticket.
            cursor.execute(
                """
                INSERT INTO public.pending_actions (
                    customer_id,
                    action_type,
                    payload
                )
                VALUES (%s, %s, %s)
                RETURNING
                    id,
                    action_type,
                    payload,
                    status,
                    created_at,
                    expires_at;
                """,
                (
                    customer_id,
                    "create_support_ticket",
                    Jsonb(payload)
                )
            )

            action = cursor.fetchone()

    return {
        "action_id": action["id"],
        "action_type": action["action_type"],
        "payload": action["payload"],
        "status": action["status"],
        "created_at": action["created_at"],
        "expires_at": action["expires_at"]
    }


# Helper function to lock a pending action for a given customer and action ID.
# This function will lock the row in the database to prevent concurrent modifications and verify that the action belongs to the customer.
# It will raise an HTTPException if the action is not found or does not belong to the customer.
# using FOR UPDATE to lock the row in the database.
# lock the row in the database to prevent concurrent modifications and verify that the action belongs to the customer.
# steps of the function:
# 1. Lock the row in the database using FOR UPDATE.
# 2. Verify that the action belongs to the customer.
# 3. Return the action if it is found and belongs to the customer.

def get_locked_pending_action(
    cursor,
    action_id: str,
    customer_id: int
):
    # 1. Lock the row in the database using FOR UPDATE.
    # 2. Verify that the action belongs to the customer.

    cursor.execute(
        """
        SELECT *
        FROM public.pending_actions
        WHERE id = %s
          AND customer_id = %s
        FOR UPDATE;
        """,
        (action_id, customer_id)
    )

    action = cursor.fetchone()

    if action is None:
        raise HTTPException(
            status_code=404,
            detail="Action not found"
        )

    return action

# Function to confirm a pending support ticket action for a given customer and action ID.
# This function will create the actual support ticket and mark the action as completed.
# It will also handle idempotency, expiration, and ownership checks.
# steps of the function:
# 1. Lock the action and verify ownership.  
# 2. Verify action type.  
# 3. Idempotency: return existing result if already completed.      
# 4. Reject non-pending actions.
# 5. Check expiration using database time.
# 6. Read the prepared payload.
# 7. Recheck order ownership.
# 8. Create the real support ticket.
# 9. Mark the action as completed.

def confirm_support_ticket(
    customer_id: int,
    action_id: str
):
    with psycopg.connect(database_url) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:

            # 1. Lock the action and verify ownership.
            action = get_locked_pending_action(
                cursor=cursor, 
                action_id=action_id,
                customer_id=customer_id
            )

            # 2. Verify action type.
            if action["action_type"] != "create_support_ticket":
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported action type"
                )

            # 3. Idempotency: return existing result.
            if action["status"] == "completed":
                return {
                    "action_id": action["id"],
                    "ticket_id": action["result_ticket_id"],
                    "status": "completed",
                    "already_completed": True
                }

            # 4. Reject non-pending actions.
            if action["status"] != "pending":
                raise HTTPException(
                    status_code=409, 
                    detail="Action is not pending"
                )

            # 5. Check expiration using database time.
            cursor.execute(
                "SELECT clock_timestamp() AS current_time;"
            )
            # Fetch the current time from the database
            current_time = cursor.fetchone()["current_time"]
            # Compare it with the action's expiration time
            if current_time >= action["expires_at"]:
                raise HTTPException(
                    status_code=410,
                    detail="Action has expired. Please prepare a new action."
                )

            # 6. Read the prepared payload.
            payload = action["payload"]

            order_number = payload["order_number"]
            subject = payload["subject"]
            description = payload["description"]

            # 7. Recheck order ownership.
            # This is a safety measure to ensure that the order still belongs to the customer at the time of confirmation.
            
            order_id = get_owned_order_id(
                cursor=cursor,
                customer_id=customer_id,
                order_number=order_number
            )

            # 8. Create the real support ticket.
            # This step is done within the same transaction to ensure atomicity.
            cursor.execute(
                """
                INSERT INTO public.support_tickets (
                    customer_id,
                    order_id,
                    subject,
                    description
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    customer_id,
                    order_id,
                    subject,
                    description
                )
            )

            ticket_id = cursor.fetchone()["id"]

            # 9. Mark the action as completed.
            
            cursor.execute(
                """
                UPDATE public.pending_actions
                SET
                    status = 'completed',
                    result_ticket_id = %s,
                    completed_at = clock_timestamp()
                WHERE id = %s;
                """,
                (ticket_id, action["id"])
            )

    # 10. Return after successful transaction commit.
    return {
        "action_id": action["id"],
        "ticket_id": ticket_id,
        "status": "completed",
        "already_completed": False
    }

# Function to get all pending actions for a given customer.
# ste
def get_customer_pending_actions(customer_id: int):

    with psycopg.connect(database_url) as connection:

        with connection.cursor(row_factory=dict_row) as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    action_type,
                    payload,
                    status,
                    created_at,
                    expires_at
                FROM public.pending_actions
                WHERE customer_id = %s
                  AND action_type = 'create_support_ticket'
                  AND status = 'pending'
                  AND expires_at > clock_timestamp()
                ORDER BY created_at DESC, id DESC;
                """,
                (customer_id,)
            )

            actions = cursor.fetchall()

    return actions

# fuction to cancel support ticket
def cancel_support_ticket(
    customer_id: int,
    action_id: str
):
    with psycopg.connect(database_url) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:

            # 1. Lock the action and verify ownership.
            action = get_locked_pending_action(
                cursor=cursor,
                action_id=action_id,
                customer_id=customer_id
            )

            # 2. Verify action type.
            if action["action_type"] != "create_support_ticket":
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported action type"
                )

            # 3. Idempotency.
            if action["status"] == "cancelled":
                return {
                    "action_id": action["id"],
                    "status": "cancelled",
                    "already_cancelled": True
                }

            # 4. Reject non-pending actions.
            if action["status"] != "pending":
                raise HTTPException(
                    status_code=409,
                    detail="Action is not pending"
                )

            # 5. Check expiration.
            cursor.execute(
                "SELECT clock_timestamp() AS current_time;"
            )

            current_time = cursor.fetchone()["current_time"]

            if current_time >= action["expires_at"]:
                raise HTTPException(
                    status_code=410,
                    detail="Action has expired"
                )

            # 6. Cancel without creating a ticket.
            cursor.execute(
                """
                UPDATE public.pending_actions
                SET status = 'cancelled'
                WHERE id = %s;
                """,
                (action["id"],)
            )

    # 7. Return after transaction commit.
    return {
        "action_id": action["id"],
        "status": "cancelled",
        "already_cancelled": False
    }
            



    




import os
import httpx
from fastapi import Header
from dataclasses import field
from fastapi import FastAPI, HTTPException
from fastapi import Depends
from pydantic import BaseModel, Field
from security import  verify_password
from jwt_utils import create_access_token

from dependencies import get_current_user, require_admin
from services.users import get_user_by_email
from services.orders import(
     get_customer_orders ,
       get_customer_order,
         get_order_by_number )

from services.support_tickets import (
   
    prepare_support_ticket,
    confirm_support_ticket,
    get_customer_pending_actions,
    cancel_support_ticket
)
from uuid import UUID
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Customer Operations Auth Gateway",
    version="0.1.0"
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "auth-gateway"
    }
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

@app.get("/", include_in_schema=False)
def customer_chat_page():
    return FileResponse("static/index.html")


class LoginRequest(BaseModel):
    email: str
    password: str   
class SupportTicketRequest(BaseModel):
    order_number: str = Field(
        min_length=1,
        max_length=50,
    )
    subject: str = Field(
        min_length=5,
        max_length=200,
    )
    description: str = Field(

        min_length=10,
        max_length=1000,
    )
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
# login endpoint for user authentication and JWT token generation
@app.post("/login") 
def login(data: LoginRequest):
    # 1. Retrieve user by email
    user = get_user_by_email(data.email)

    # 3. Check if user exists and verify password
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
            
    stored_password = user["password_hash"]
    if verify_password(data.password, stored_password):
        # 4. Create JWT token
        access_token = create_access_token(user["id"])
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
    else:
        raise HTTPException(status_code=401, detail="Wrong email or password.")
# endpoint to get the current user's information
@app.get("/me")
def read_me(user: dict = Depends(get_current_user)):
    return user
# endpoint to get the admin dashboard, accessible only to admin users
@app.get("/admin/dashboard")
def admin_dashboard(user: dict = Depends(require_admin)):
        

    return {
        "message": "Welcome, Admin!",
        "email": user["email"]
    }
# endpoint to get the current user's orders, accessible only to customers
@app.get("/my_orders")
def my_orders(user: dict = Depends(get_current_user)):

    if user["role"] != "customer":
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )
    

    orders = get_customer_orders(user["customer_id"])
    return { "orders": orders }
# endpoint to get a specific order by ID, accessible only to customers
@app.get("/my_orders/{order_id}")
def get_order(order_id: int, user: dict = Depends(get_current_user)):

    if user["role"] != "customer":
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )
    order = get_customer_order(order_id, user["customer_id"])
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found."
        )
    return order
# endpoint to get a specific order by order number, accessible only to customers
@app.get("/my_orders/number/{order_number}")
def my_order_by_number(order_number: str, user: dict = Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )
    order = get_order_by_number(order_number, user["customer_id"])
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found."
        )
    return order

# endpoint to prepare a support ticket, accessible only to customers
@app.post("/support_ticket/prepare", status_code=201)
def prepare_ticket(
    ticket_request: SupportTicketRequest,
    user: dict = Depends(get_current_user)
):

    if user["role"] != "customer" or user["customer_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )

    action = prepare_support_ticket(
        customer_id=user["customer_id"],
        order_number=ticket_request.order_number,
        subject=ticket_request.subject,
        description=ticket_request.description
    )

    return action
# endpoint to list pending support tickets, accessible only to customers
@app.get("/support_ticket/pending")
def list_pending_support_tickets(
    user: dict = Depends(get_current_user)
):
    if user["role"] != "customer" or user["customer_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )

    actions = get_customer_pending_actions(
        customer_id=user["customer_id"]
    )

    return {"pending_actions": actions}
# endpoint to confirm a support ticket, accessible only to customers
@app.post("/support_ticket/confirm/{action_id}")
def confirm_ticket(
    action_id: str,
    user: dict = Depends(get_current_user)
):
    if user["role"] != "customer" or user["customer_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )

    return confirm_support_ticket(
        customer_id=user["customer_id"],
        action_id=str(action_id)
    )
# endpoint to chat with the AI agent, accessible only to customers
@app.post("/chat")
async def chat(
    data: ChatRequest,
    authorization: str = Header(),
    user: dict = Depends(get_current_user)
):
    # 1. Only authenticated customers can chat.
    if user["role"] != "customer" or user["customer_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )

    # 2. Build the internal n8n webhook URL.
    n8n_url = (
        os.environ["N8N_BASE_URL"].rstrip("/")
        + "/webhook/order-lookup"
    )

    # 3. Forward the message to the AI Agent.
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                n8n_url,
                headers={
                    "Authorization": authorization
                },
                json={
                    "message": data.message,
                    "sessionId": f"user-{user['id']}"
                }
            )

            response.raise_for_status()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="AI Agent response timed out."
        )

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="AI Agent is currently unavailable."
        )

    # 4. Return the agent response to the browser.
    return {
        "reply": response.text
    }
# endpoint to cancel a pending support ticket, accessible only to customers
@app.post("/support_ticket/cancel/{action_id}")
def cancel_pending_support_ticket(
    action_id: str,
    user: dict = Depends(get_current_user)
):
    if user["role"] != "customer" or user["customer_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Customer access required."
        )

    return cancel_support_ticket(
        customer_id=user["customer_id"],
        action_id=action_id
    )
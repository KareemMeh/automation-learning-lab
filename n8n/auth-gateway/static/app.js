
"use strict";

// ============================================================
// PART 1 — SHARED APPLICATION STATE
// ============================================================

// Store the authenticated customer's access token.
let accessToken = null;

// Identify the current login session.
let sessionVersion = 0;

// Check whether an asynchronous operation belongs to the current session.
function isCurrentSession(version, token) {
    return (
        sessionVersion === version &&
        accessToken === token &&
        token !== null
    );
}


// ============================================================
// PART 2 — LOGIN FEATURE
// DOM elements + Event + API request
// ============================================================

// 2.1 — Login DOM elements

const loginForm = document.getElementById("loginForm");
const loginButton = document.getElementById("loginButton");
const loginMessage = document.getElementById("loginMessage");
const loginScreen = document.getElementById("loginScreen");
const chatScreen = document.getElementById("chatScreen");


// 2.2 — Login submit event

loginForm.addEventListener("submit", async (event) => {

    // Prevent the browser from submitting the form normally.
    event.preventDefault();

    // Read customer credentials from the form.
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    // Reset the login message.
    loginMessage.textContent = "";
    loginMessage.className = "";

    // Prevent duplicate login submissions.
    loginButton.disabled = true;
    loginButton.textContent = "جاري تسجيل الدخول...";

    // Capture the session version before the request starts.
    const requestVersion = sessionVersion;

    try {

        // Send customer credentials to FastAPI.
        const response = await fetch("/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        // Ignore a response from an outdated session.
        if (requestVersion !== sessionVersion) return;

        // Handle invalid credentials.
        if (response.status === 401) {
            throw new Error(
                "البريد الإلكتروني أو كلمة المرور غير صحيحة."
            );
        }

        // Handle other HTTP errors.
        if (!response.ok) {
            throw new Error(
                "حصلت مشكلة في السيرفر. حاول مرة تانية."
            );
        }

        // Parse the JSON response.
        const data = await response.json();

        // Check the session again after awaiting JSON parsing.
        if (requestVersion !== sessionVersion) return;

        // Validate the returned access token.
        if (
            typeof data.access_token !== "string" ||
            !data.access_token
        ) {
            throw new Error(
                "السيرفر مرجعش بيانات تسجيل دخول صحيحة."
            );
        }

        // Start a new authenticated session.
        sessionVersion += 1;
        accessToken = data.access_token;

        // Reset the chat interface for the new session.
        resetChatUI();

        // Show the login success message.
        loginMessage.textContent = "تم تسجيل الدخول بنجاح!";
        loginMessage.className = "success";

        // Switch from the login screen to the chat screen.
        loginScreen.hidden = true;
        chatScreen.hidden = false;

        // Load any pending approvals belonging to this customer.
        const loggedInVersion = sessionVersion;
        const loggedInToken = accessToken;

        try {
            await loadLatestPendingApproval();
        } catch (error) {
            console.error(
                "Could not load pending approvals:",
                error.message
            );

            if (isCurrentSession(loggedInVersion, loggedInToken)) {
                addMessage(
                    "تعذر تحميل طلبات الموافقة المعلقة حاليًا.",
                    "assistant"
                );
            }
        }

    } catch (error) {

        // Ignore errors from an outdated login attempt.
        if (requestVersion !== sessionVersion) return;

        accessToken = null;

        loginMessage.textContent = error.message;
        loginMessage.className = "error";

    } finally {

        // Restore the login button if this attempt still owns it.
        if (
            requestVersion === sessionVersion ||
            isCurrentSession(sessionVersion, accessToken)
        ) {
            loginButton.disabled = false;
            loginButton.textContent = "تسجيل الدخول";
        }
    }
});


// ============================================================
// PART 3 — LOGOUT FEATURE
// DOM elements + Event
// ============================================================

// 3.1 — Logout DOM element

const logoutButton = document.getElementById("logoutButton");


// 3.2 — Logout click event

logoutButton.addEventListener("click", () => {

    // Invalidate the previous session.
    sessionVersion += 1;

    // Remove the access token from application state.
    accessToken = null;

    // Clear the previous customer's chat and approvals.
    resetChatUI();

    // Return to the login screen.
    loginScreen.hidden = false;
    chatScreen.hidden = true;

    // Clear the login form.
    loginForm.reset();

    // Clear previous login messages.
    loginMessage.textContent = "";
    loginMessage.className = "";

    // Restore the login button.
    loginButton.disabled = false;
    loginButton.textContent = "تسجيل الدخول";
});


// ============================================================
// PART 4 — CHAT FEATURE
// DOM elements + Functions + Event + API request
// ============================================================

// 4.1 — Chat DOM elements

const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("sendButton");


// 4.2 — Reset the chat interface

function resetChatUI() {

    // Create the welcome message.
    const welcomeMessage = document.createElement("div");

    welcomeMessage.className = "message assistant-message";

    welcomeMessage.textContent =
        "أهلًا بحضرتك، إزاي أقدر أساعدك في متابعة طلباتك أو تقديم شكوى؟";

    // Clear previous messages.
    chatMessages.replaceChildren();

    // Add the welcome message.
    chatMessages.appendChild(welcomeMessage);

    // Restore the approval area if it belongs inside chatMessages.
    if (approvalArea.parentElement !== chatMessages) {
        chatMessages.appendChild(approvalArea);
    }

    // Clear and hide pending approval cards.
    approvalArea.replaceChildren();
    approvalArea.hidden = true;

    // Reset chat controls.
    chatInput.value = "";
    sendButton.disabled = false;
}


// 4.3 — Add a message to the chat interface

function addMessage(text, role) {

    // Create a new message element.
    const messageElement = document.createElement("div");

    // Apply a different CSS class for user and assistant messages.
    messageElement.className =
        role === "user"
            ? "message user-message"
            : "message assistant-message";

    // Insert the message text safely.
    messageElement.textContent = text;

    // Display the message.
    chatMessages.appendChild(messageElement);

    // Scroll to the latest message.
    chatMessages.scrollTop = chatMessages.scrollHeight;
}


// 4.4 — Chat submit event

chatForm.addEventListener("submit", async (event) => {

    // Prevent normal form submission.
    event.preventDefault();

    // Read the customer's message.
    const message = chatInput.value.trim();

    // Stop if the message is empty or the customer is not logged in.
    if (!message || !accessToken) return;

    // Capture the current session.
    const token = accessToken;
    const version = sessionVersion;

    // Display the customer's message.
    addMessage(message, "user");

    // Clear the input field.
    chatInput.value = "";

    // Disable the send button while waiting.
    sendButton.disabled = true;

    try {

        // Send the message to FastAPI.
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                message: message
            })
        });

        // Ignore responses from an outdated session.
        if (!isCurrentSession(version, token)) return;

        // Validate the HTTP response.
        if (!response.ok) {
            throw new Error(
                `Chat request failed: HTTP ${response.status}`
            );
        }

        // Read the assistant's reply.
        const data = await response.json();

        // Check the session again after parsing the response.
        if (!isCurrentSession(version, token)) return;

        // Display the assistant's reply.
        addMessage(data.reply, "assistant");
        // Refresh pending approvals after the AI Agent responds.
        try {
            await loadLatestPendingApproval(version, token);
        } catch (approvalError) {
            console.error(
                "Failed to load pending approvals:",
                approvalError.message
            );
        }

    } catch (error) {

        // Display an error only for the active session.
        if (isCurrentSession(version, token)) {
            addMessage(
                "عذرًا، حصلت مشكلة في الاتصال. حاول مرة تانية.",
                "assistant"
            );
        }

    } finally {

        // Restore the chat controls for the active session.
        if (isCurrentSession(version, token)) {
            sendButton.disabled = false;
            chatInput.focus();
        }
    }
});


// ============================================================
// PART 5 — HUMAN APPROVAL FEATURE
// DOM elements + API functions + Rendering + Button events
// ============================================================

// 5.1 — Approval DOM elements

const approvalArea = document.getElementById("approvalArea");


// ------------------------------------------------------------
// 5.2 — Get pending actions from FastAPI
// ------------------------------------------------------------

async function getPendingActions(token) {

    // Request the customer's pending approval actions.
    const response = await fetch("/support_ticket/pending", {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${token}`
        }
    });

    // Validate the HTTP response.
    if (!response.ok) {
        throw new Error(
            `Failed to load pending actions: HTTP ${response.status}`
        );
    }

    // Parse the JSON response.
    const data = await response.json();

    // Validate the pending_actions array.
    if (!Array.isArray(data.pending_actions)) {
        throw new Error("Invalid pending actions response.");
    }

    return data.pending_actions;
}


// ------------------------------------------------------------
// 5.3 — Confirm a pending support ticket
// ------------------------------------------------------------

async function confirmPendingApproval(actionId, token) {

    // Send the confirmation request to FastAPI.
    const response = await fetch(
        `/support_ticket/confirm/${encodeURIComponent(actionId)}`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    // Handle HTTP errors.
    if (!response.ok) {
        throw new Error(
            `Confirmation failed with HTTP ${response.status}`
        );
    }

    // Return the confirmation result.
    return await response.json();
}


// ------------------------------------------------------------
// 5.4 — Cancel a pending support ticket
// ------------------------------------------------------------

async function cancelPendingApproval(actionId, token) {

    // Send the cancellation request to FastAPI.
    const response = await fetch(
        `/support_ticket/cancel/${encodeURIComponent(actionId)}`,
        {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }
    );

    // Handle HTTP errors.
    if (!response.ok) {
        throw new Error(
            `Cancellation failed with HTTP ${response.status}`
        );
    }

    // Return the cancellation result.
    return await response.json();
}


// ------------------------------------------------------------
// 5.5 — Render the pending approval card
// ------------------------------------------------------------

function renderPendingApproval(action, version, token) {

    // Stop if the session is no longer valid.
    if (!isCurrentSession(version, token)) return;

    // Remove the previous approval card.
    approvalArea.replaceChildren();

    // Create the approval card.
    const card = document.createElement("div");
    card.className = "approval-card";

    // Create the card title.
    const title = document.createElement("h3");
    title.textContent = "مراجعة طلب الشكوى";

    // Display the order number.
    const order = document.createElement("p");
    order.textContent =
        `رقم الأوردر: ${action.payload.order_number}`;

    // Display the ticket subject.
    const subject = document.createElement("p");
    subject.textContent =
        `الموضوع: ${action.payload.subject}`;

    // Display the ticket description.
    const description = document.createElement("p");
    description.textContent =
        `الوصف: ${action.payload.description}`;

    // Display the current approval status.
    const status = document.createElement("p");
    status.textContent = "الحالة: بانتظار موافقتك";

    // Create the confirmation button.
    const confirmButton = document.createElement("button");
    confirmButton.type = "button";
    confirmButton.className = "approval-confirm-button";
    confirmButton.textContent = "تأكيد الشكوى";

    // Create the cancellation button.
    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "approval-cancel-button";
    cancelButton.textContent = "إلغاء الشكوى";


    // --------------------------------------------------------
    // 5.6 — Confirm button click event
    // --------------------------------------------------------

    confirmButton.addEventListener("click", async () => {

        // Validate the current session.
        if (!isCurrentSession(version, token)) return;

        // Ask the customer for final confirmation.
        const approved = window.confirm(
            "هل تؤكد إنشاء تذكرة الشكوى بالتفاصيل المعروضة؟"
        );

        if (!approved) return;

        // Prevent duplicate button clicks.
        confirmButton.disabled = true;
        cancelButton.disabled = true;

        confirmButton.textContent = "جاري التأكيد...";

        try {

            // Execute the confirmation API request.
            const result = await confirmPendingApproval(
                action.id,
                token
            );

            // Ignore results from an outdated session.
            if (!isCurrentSession(version, token)) return;

            // Validate the backend confirmation status.
            if (result.status !== "completed") {
                throw new Error(
                    "Unexpected confirmation status."
                );
            }

            // Update the approval card.
            status.textContent =
                "الحالة: تم إنشاء الشكوى بنجاح";

            confirmButton.textContent = "تم التأكيد";

            // Notify the customer in the chat.
            addMessage(
                `تم تسجيل الشكوى بنجاح. رقم التذكرة: ${result.ticket_id}`,
                "assistant"
            );

        } catch (error) {

            if (!isCurrentSession(version, token)) return;

            // The server may have completed the request despite a network error.
            status.textContent =
                "تعذر التأكد من نتيجة العملية. راجع حالة الطلب قبل المحاولة مجددًا.";

            confirmButton.textContent = "النتيجة غير مؤكدة";
        }
    });


    // --------------------------------------------------------
    // 5.7 — Cancel button click event
    // --------------------------------------------------------

    cancelButton.addEventListener("click", async () => {

        // Validate the current session.
        if (!isCurrentSession(version, token)) return;

        // Ask the customer to confirm cancellation.
        const accepted = window.confirm(
            "هل تريد إلغاء طلب الشكوى؟"
        );

        if (!accepted) return;

        // Prevent duplicate button clicks.
        confirmButton.disabled = true;
        cancelButton.disabled = true;

        cancelButton.textContent = "جاري الإلغاء...";

        try {

            // Execute the cancellation API request.
            const result = await cancelPendingApproval(
                action.id,
                token
            );

            // Ignore results from an outdated session.
            if (!isCurrentSession(version, token)) return;

            // Validate the backend cancellation status.
            if (result.status !== "cancelled") {
                throw new Error(
                    "Unexpected cancellation status."
                );
            }

            // Update the approval card.
            status.textContent =
                "الحالة: تم إلغاء طلب الشكوى";

            cancelButton.textContent = "تم الإلغاء";

            // Notify the customer in the chat.
            addMessage(
                "تم إلغاء طلب الشكوى، ولم يتم إنشاء تذكرة.",
                "assistant"
            );

        } catch (error) {

            if (!isCurrentSession(version, token)) return;

            // The cancellation result may be uncertain after a network error.
            status.textContent =
                "تعذر التأكد من نتيجة الإلغاء. راجع حالة الطلب قبل المحاولة مجددًا.";

            cancelButton.textContent = "النتيجة غير مؤكدة";
        }
    });


    // --------------------------------------------------------
    // 5.8 — Attach the approval card to the page
    // --------------------------------------------------------

    // Add all elements to the card.
   card.append(
    title,
    order,
    subject,
    description,
    status,
    confirmButton,
    cancelButton
);

    // Add the approval card.
    approvalArea.appendChild(card);

    // Move the approval area after the latest chat message.
    chatMessages.appendChild(approvalArea);

    // Make the approval area visible.
    approvalArea.hidden = false;

    // Scroll to the approval card.
    approvalArea.scrollIntoView({
        behavior: "smooth",
        block: "end"
    });
}



// ============================================================
// PART 6 — APPROVAL LOADING
// Load latest approval + Load approval by ID + Test event
// ============================================================

// 6.1 — Load the latest pending approval after login.

async function loadLatestPendingApproval() {

    // Capture the current authenticated session.
    const token = accessToken;
    const version = sessionVersion;

    // Stop if the customer is not authenticated.
    if (!token) return;

    // Request pending actions from FastAPI.
    const actions = await getPendingActions(token);

    // Ignore results from an outdated session.
    if (!isCurrentSession(version, token)) return;

    // Hide the approval area when no pending actions exist.
    if (actions.length === 0) {
        approvalArea.replaceChildren();
        approvalArea.hidden = true;
        return;
    }

    // The backend returns pending actions ordered by creation time.
    const latestAction = actions[0];

    // Render the latest pending action.
    renderPendingApproval(
        latestAction,
        version,
        token
    );
}







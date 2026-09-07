const API_URL = "http://127.0.0.1:8000";

// =========================================================
// SESSION
// =========================================================

let accessToken = null;


// =========================================================
// ELEMENTS
// =========================================================

const loginScreen = document.getElementById("loginScreen");
const dashboardScreen = document.getElementById("dashboardScreen");

const loginForm = document.getElementById("loginForm");
const paymentForm = document.getElementById("paymentForm");

const loginMessage = document.getElementById("loginMessage");
const paymentMessage = document.getElementById("paymentMessage");

const paymentsTable = document.getElementById("paymentsTable");

const eventsPanel = document.getElementById("eventsPanel");
const eventsList = document.getElementById("eventsList");
const selectedPayment = document.getElementById("selectedPayment");


// =========================================================
// SHOW LOGIN
// =========================================================

function showLogin() {

    dashboardScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");

    loginForm.reset();

    loginMessage.textContent = "";
    paymentMessage.textContent = "";

    eventsPanel.classList.add("hidden");
}


// =========================================================
// SHOW DASHBOARD
// =========================================================

async function showDashboard() {

    loginScreen.classList.add("hidden");
    dashboardScreen.classList.remove("hidden");

    await loadDashboard();
    await loadPayments();
}


// =========================================================
// API REQUEST
// =========================================================

async function apiRequest(endpoint, options = {}) {

    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };


    // Add JWT token when available
    if (accessToken) {

        headers["Authorization"] =
            `Bearer ${accessToken}`;
    }


    let response;


    try {

        response = await fetch(
            `${API_URL}${endpoint}`,
            {
                ...options,
                headers
            }
        );

    } catch (error) {

        throw new Error(
            "Cannot connect to the backend. Make sure Uvicorn is running on http://127.0.0.1:8000"
        );
    }


    // -----------------------------------------------------
    // Read response
    // -----------------------------------------------------

    let data = null;

    try {

        data = await response.json();

    } catch {

        data = null;
    }


    // -----------------------------------------------------
    // Authentication error
    // -----------------------------------------------------

    if (response.status === 401) {

        accessToken = null;

        showLogin();

        throw new Error(
            "Authentication failed. Please login again."
        );
    }


    // -----------------------------------------------------
    // Other API errors
    // -----------------------------------------------------

    if (!response.ok) {

        throw new Error(
            data?.detail ||
            "Request failed"
        );
    }


    return data;
}


// =========================================================
// LOGIN
// =========================================================

loginForm.addEventListener(
    "submit",
    async (event) => {

        event.preventDefault();


        loginMessage.textContent =
            "Signing in...";


        const username =
            document.getElementById(
                "username"
            ).value.trim();


        const password =
            document.getElementById(
                "password"
            ).value;


        try {

            const data =
                await apiRequest(
                    "/login",
                    {
                        method: "POST",

                        body: JSON.stringify({
                            username: username,
                            password: password
                        })
                    }
                );


            // -------------------------------------------------
            // Store JWT token
            // -------------------------------------------------

            accessToken =
                data.access_token;


            console.log(
                "Login token received:",
                !!accessToken
            );


            if (!accessToken) {

                throw new Error(
                    "Login succeeded but no access token was returned."
                );
            }


            loginMessage.textContent =
                "Login successful.";


            // -------------------------------------------------
            // Open dashboard
            // -------------------------------------------------

            await showDashboard();


        } catch (error) {

            console.error(
                "Login error:",
                error
            );


            loginMessage.textContent =
                error.message;
        }
    }
);


// =========================================================
// DASHBOARD STATISTICS
// =========================================================

async function loadDashboard() {

    try {

        const data =
            await apiRequest(
                "/dashboard"
            );


        document.getElementById(
            "totalPayments"
        ).textContent =
            data.total_payments;


        document.getElementById(
            "completedPayments"
        ).textContent =
            data.completed_payments;


        document.getElementById(
            "failedPayments"
        ).textContent =
            data.failed_payments;


        document.getElementById(
            "pendingPayments"
        ).textContent =
            data.pending_payments;


        document.getElementById(
            "totalAmount"
        ).textContent =
            Number(
                data.total_amount || 0
            ).toFixed(2);


    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );


        // Do not overwrite authentication error
        if (accessToken) {

            paymentMessage.textContent =
                error.message;
        }
    }
}


// =========================================================
// PAYMENT HISTORY
// =========================================================

async function loadPayments() {

    paymentsTable.innerHTML = `
        <tr>
            <td colspan="8" class="empty">
                Loading payments...
            </td>
        </tr>
    `;


    try {

        const payments =
            await apiRequest(
                "/payments"
            );


        if (
            !payments ||
            payments.length === 0
        ) {

            paymentsTable.innerHTML = `
                <tr>
                    <td colspan="8" class="empty">
                        No payments found.
                    </td>
                </tr>
            `;

            return;
        }


        paymentsTable.innerHTML = "";


        payments.forEach(
            (payment) => {

                const row =
                    document.createElement(
                        "tr"
                    );


                const status =
                    String(
                        payment.status || ""
                    );


                const statusClass =
                    status
                        .toLowerCase()
                        .replaceAll(
                            "_",
                            "-"
                        );


                // -------------------------------------------------
                // Retry button
                // -------------------------------------------------

                let retryButton = "";


                if (
                    status === "FAILED" ||
                    status === "PERMANENTLY_FAILED"
                ) {

                    retryButton = `
                        <button
                            class="retry-button"
                            type="button"
                            onclick="retryPayment('${payment.payment_id}')"
                        >
                            Retry
                        </button>
                    `;
                }


                row.innerHTML = `
                    <td>
                        <strong>
                            ${payment.payment_id || "-"}
                        </strong>
                    </td>

                    <td>
                        ${Number(
                            payment.amount || 0
                        ).toFixed(2)}
                    </td>

                    <td>
                        ${payment.currency || "-"}
                    </td>

                    <td>
                        <span class="status ${statusClass}">
                            ${status || "-"}
                        </span>
                    </td>

                    <td>
                        ${payment.retry_count ?? 0}
                    </td>

                    <td>
                        ${formatDate(
                            payment.created_at
                        )}
                    </td>

                    <td>
                        <button
                            class="event-button"
                            type="button"
                            onclick="viewEvents('${payment.payment_id}')"
                        >
                            View Events
                        </button>
                    </td>

                    <td>
                        ${retryButton}
                    </td>
                `;


                paymentsTable.appendChild(
                    row
                );
            }
        );


    } catch (error) {

        paymentsTable.innerHTML = `
            <tr>
                <td colspan="8" class="empty">
                    Failed to load payments.
                </td>
            </tr>
        `;


        console.error(
            "Payment history error:",
            error
        );
    }
}


// =========================================================
// CREATE PAYMENT
// =========================================================

paymentForm.addEventListener(
    "submit",
    async (event) => {

        event.preventDefault();


        paymentMessage.textContent =
            "Creating payment...";


        const amount =
            Number(
                document.getElementById(
                    "amount"
                ).value
            );


        const currency =
            document.getElementById(
                "currency"
            ).value;


        const idempotencyKey =
            document.getElementById(
                "idempotencyKey"
            ).value.trim();


        // -------------------------------------------------
        // Validate amount
        // -------------------------------------------------

        if (
            !amount ||
            amount <= 0
        ) {

            paymentMessage.textContent =
                "Please enter a valid amount.";

            return;
        }


        // -------------------------------------------------
        // Validate idempotency key
        // -------------------------------------------------

        if (!idempotencyKey) {

            paymentMessage.textContent =
                "Please enter an idempotency key.";

            return;
        }


        try {

            const payment =
                await apiRequest(
                    "/payments",
                    {
                        method: "POST",

                        body: JSON.stringify({
                            amount: amount,
                            currency: currency,
                            idempotency_key:
                                idempotencyKey
                        })
                    }
                );


            paymentMessage.innerHTML = `
                Payment created successfully.
                <strong>
                    ${payment.payment_id}
                </strong>
            `;


            // Clear form
            paymentForm.reset();


            // Reload dashboard
            await loadDashboard();

            await loadPayments();


        } catch (error) {

            console.error(
                "Create payment error:",
                error
            );


            paymentMessage.textContent =
                error.message;
        }
    }
);


// =========================================================
// RETRY PAYMENT
// =========================================================

async function retryPayment(paymentId) {

    const confirmed =
        window.confirm(
            `Retry payment ${paymentId}?`
        );


    if (!confirmed) {

        return;
    }


    paymentMessage.textContent =
        `Retrying payment ${paymentId}...`;


    try {

        const payment =
            await apiRequest(
                `/payments/${paymentId}/retry`,
                {
                    method: "POST"
                }
            );


        paymentMessage.innerHTML = `
            Payment retry successful.
            <strong>
                ${payment.payment_id}
            </strong>
            is now
            <strong>
                ${payment.status}
            </strong>.
        `;


        await loadDashboard();

        await loadPayments();


        // Show updated event history
        await viewEvents(
            payment.payment_id
        );


    } catch (error) {

        console.error(
            "Retry error:",
            error
        );


        paymentMessage.textContent =
            `Retry failed: ${error.message}`;
    }
}


// =========================================================
// VIEW PAYMENT EVENTS
// =========================================================

async function viewEvents(
    paymentId
) {

    eventsPanel.classList.remove(
        "hidden"
    );


    selectedPayment.textContent =
        `Event history for ${paymentId}`;


    eventsList.innerHTML =
        "<p>Loading events...</p>";


    try {

        const events =
            await apiRequest(
                `/payments/${paymentId}/events`
            );


        if (
            !events ||
            events.length === 0
        ) {

            eventsList.innerHTML =
                "<p>No events found.</p>";

            return;
        }


        eventsList.innerHTML = "";


        events.forEach(
            (event) => {

                const eventElement =
                    document.createElement(
                        "div"
                    );


                eventElement.className =
                    "event-item";


                eventElement.innerHTML = `
                    <div class="event-type">
                        ${event.event_type || "-"}
                    </div>

                    <div class="event-message">
                        ${event.message || ""}
                    </div>

                    <div class="event-time">
                        ${formatDate(
                            event.created_at
                        )}
                    </div>
                `;


                eventsList.appendChild(
                    eventElement
                );
            }
        );


    } catch (error) {

        console.error(
            "Events error:",
            error
        );


        eventsList.innerHTML = `
            <p>
                Failed to load events:
                ${error.message}
            </p>
        `;
    }
}


// =========================================================
// CLOSE EVENTS
// =========================================================

document.getElementById(
    "closeEvents"
).addEventListener(
    "click",
    () => {

        eventsPanel.classList.add(
            "hidden"
        );
    }
);


// =========================================================
// REFRESH
// =========================================================

document.getElementById(
    "refreshButton"
).addEventListener(
    "click",
    async () => {

        await loadDashboard();

        await loadPayments();
    }
);


// =========================================================
// LOGOUT
// =========================================================

function logout() {

    accessToken = null;

    showLogin();
}


document.getElementById(
    "logoutButton"
).addEventListener(
    "click",
    logout
);


// =========================================================
// DATE FORMAT
// =========================================================

function formatDate(
    dateString
) {

    if (!dateString) {

        return "-";
    }


    const date =
        new Date(dateString);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return "-";
    }


    return date.toLocaleString();
}


// =========================================================
// START APPLICATION
// =========================================================

// Always start at login screen.

showLogin();

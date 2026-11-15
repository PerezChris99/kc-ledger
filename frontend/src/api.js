export class ApiError extends Error {
    status;
    constructor(message, status) { super(message); this.status = status; }
}
async function csrf() {
    const response = await fetch("/api/csrf", { credentials: "include" });
    if (!response.ok)
        throw new ApiError("Could not establish a secure session.", response.status);
    const body = await response.json();
    return body.csrfToken;
}
export async function api(path, init = {}) {
    const method = (init.method ?? "GET").toUpperCase();
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body)
        headers.set("Content-Type", "application/json");
    if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method))
        headers.set("X-CSRFToken", await csrf());
    const response = await fetch(path, { ...init, method, headers, credentials: "include" });
    if (!response.ok) {
        let message = "Request failed.";
        try {
            const body = await response.json();
            message = body.detail ?? body.message ?? message;
        }
        catch { /* Response may not be JSON. */ }
        throw new ApiError(message, response.status);
    }
    return response.json();
}
export const money = (value, currency = "USD") => {
    const amount = Number(value ?? 0);
    if (!Number.isFinite(amount))
        return "—";
    try {
        return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
    }
    catch {
        return `${currency} ${amount.toFixed(2)}`;
    }
};

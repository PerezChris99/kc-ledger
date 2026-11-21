export class ApiError extends Error {
    status;
    constructor(message, status) { super(message); this.status = status; }
}
async function csrf() {
    let response;
    try {
        response = await fetch("/api/csrf", { credentials: "include", cache: "no-store" });
    } catch (error) {
        if (error instanceof TypeError)
            throw new ApiError("Cannot contact the secure session API. Changes were not submitted.", 0);
        throw error;
    }
    if (!response.ok)
        throw new ApiError("Could not establish a secure session.", response.status);
    const body = await response.json();
    return body.csrfToken;
}
export async function api(path, init = {}) {
    if (navigator.onLine === false)
        throw new ApiError("Offline: financial records and updates require a live secure connection.", 0);
    const method = (init.method ?? "GET").toUpperCase();
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body)
        headers.set("Content-Type", "application/json");
    if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method))
        headers.set("X-CSRFToken", await csrf());
    let response;
    try {
        response = await fetch(path, { ...init, method, headers, credentials: "include", cache: "no-store" });
    } catch (error) {
        if (error instanceof TypeError)
            throw new ApiError("Cannot reach the private KC Ledger server. Check your connection; no changes were queued.", 0);
        throw error;
    }
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

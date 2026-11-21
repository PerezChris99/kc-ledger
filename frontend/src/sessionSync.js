/** Ephemeral same-origin session coordination: no customer data or credentials. */
const CHANNEL = "kc-ledger-session-v1";

export function announceSessionEnded() {
    if (!("BroadcastChannel" in window)) return;
    const channel = new BroadcastChannel(CHANNEL);
    try {
        channel.postMessage({ type: "session-ended" });
    } finally {
        channel.close();
    }
}

export function listenForSessionEnd(callback) {
    if (!("BroadcastChannel" in window)) return () => {};
    const channel = new BroadcastChannel(CHANNEL);
    channel.onmessage = (event) => {
        if (event.data?.type === "session-ended") callback();
    };
    return () => channel.close();
}

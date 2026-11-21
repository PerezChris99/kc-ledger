import { useEffect, useState } from "react";
import { Download, Smartphone, X } from "lucide-react";

function isInstalled() {
    return window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true;
}
function isIos() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}
export default function InstallPrompt() {
    const [installEvent, setInstallEvent] = useState(null);
    const [installed, setInstalled] = useState(isInstalled);
    const [manual, setManual] = useState(false);
    const [ios, setIos] = useState(isIos);
    useEffect(() => {
        const onPrompt = (event) => {
            event.preventDefault();
            if (!isInstalled()) setInstallEvent(event);
        };
        const onInstalled = () => {
            setInstalled(true);
            setInstallEvent(null);
            setManual(false);
        };
        const display = window.matchMedia("(display-mode: standalone)");
        const onDisplayChange = () => setInstalled(isInstalled());
        window.addEventListener("beforeinstallprompt", onPrompt);
        window.addEventListener("appinstalled", onInstalled);
        display.addEventListener?.("change", onDisplayChange);
        setIos(isIos());
        return () => {
            window.removeEventListener("beforeinstallprompt", onPrompt);
            window.removeEventListener("appinstalled", onInstalled);
            display.removeEventListener?.("change", onDisplayChange);
        };
    }, []);
    if (installed) return null;
    // Browsers may offer installation only through their own menu. Keep
    // instructions discoverable even without beforeinstallprompt.
    async function install() {
        if (!installEvent) {
            setManual(true);
            return;
        }
        const prompt = installEvent;
        setInstallEvent(null);
        try {
            await prompt.prompt();
            const response = await prompt.userChoice;
            if (response.outcome === "accepted") setInstalled(true);
        } catch {
            // Browser controls the install UI; user can install from its menu.
        }
    }
    return <div className="pwa-install-anchor">
      <button type="button" className="install-button" onClick={install}
        aria-label={installEvent ? "Install KC Ledger as an app" : "Show app installation instructions"}>
        <Download size={14}/> {installEvent ? "Install app" : "Install guide"}</button>
      {manual && <div className="pwa-install-instructions" role="note">
        <button type="button" className="pwa-close-icon" aria-label="Close installation help"
          onClick={() => setManual(false)}><X size={15}/></button>
        <Smartphone size={16}/>
        {ios ? <p>On iPhone or iPad: open in Safari, tap <strong>Share</strong>,
            then <strong>Add to Home Screen</strong> and choose <strong>Open as Web App</strong>
            when offered.</p>
          : <p>In Chrome or Edge, open the browser menu and choose <strong>Install app</strong>
            (or <strong>Apps → Install this site as an app</strong>). Installation
            options depend on browser and device.</p>}
      </div>}
    </div>;
}

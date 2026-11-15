import { useEffect, useState } from "react";
import { Download } from "lucide-react";
export default function InstallPrompt() {
    const [installEvent, setInstallEvent] = useState(null);
    const [installed, setInstalled] = useState(false);
    useEffect(() => {
        const onPrompt = (event) => {
            event.preventDefault();
            setInstallEvent(event);
        };
        const onInstalled = () => { setInstalled(true); setInstallEvent(null); };
        window.addEventListener("beforeinstallprompt", onPrompt);
        window.addEventListener("appinstalled", onInstalled);
        return () => { window.removeEventListener("beforeinstallprompt", onPrompt); window.removeEventListener("appinstalled", onInstalled); };
    }, []);
    if (installed || !installEvent)
        return null;
    return <button className="install-button" onClick={async () => {
            await installEvent.prompt();
            const choice = await installEvent.userChoice;
            if (choice.outcome === "accepted")
                setInstallEvent(null);
        }}><Download size={14}/> Install app</button>;
}

import { useState } from "react";
import { useRegisterSW } from "virtual:pwa-register/react";
import { RefreshCw, X } from "lucide-react";

export default function PwaControls() {
    const [dismissOfflineReady, setDismissOfflineReady] = useState(false);
    const [updateError, setUpdateError] = useState("");
    const {
        offlineReady: [offlineReady, setOfflineReady],
        needRefresh: [needRefresh, setNeedRefresh],
        updateServiceWorker,
    } = useRegisterSW({
        onRegisterError: () => setUpdateError("App update service unavailable. Reload while online."),
    });
    const showStatus = (offlineReady && !dismissOfflineReady) || needRefresh || updateError;
    async function update() {
        try {
            setUpdateError("");
            await updateServiceWorker(true);
        } catch {
            setUpdateError("Update could not be applied. Check your connection and retry.");
        }
    }
    return <>
      {showStatus && <div className="pwa-update-notice" role="status" aria-live="polite">
        <div>
          <strong>{needRefresh ? "A newer KC Ledger version is ready" :
              updateError ? "App update needs attention" : "KC Ledger is installed for offline launch"}</strong>
          <p>{needRefresh ? "Save any unfinished edits, then reload into the tested update." :
              updateError || "The app interface is available offline. Private financial records and changes still require the backend."}</p>
        </div>
        {needRefresh && <button type="button" className="small-button"
          onClick={() => void update()}><RefreshCw size={14}/> Update now</button>}
        <button type="button" className="pwa-close-icon" aria-label="Dismiss app update notice"
          onClick={() => {
              setOfflineReady(false);
              setNeedRefresh(false);
              setDismissOfflineReady(true);
              setUpdateError("");
          }}><X size={17}/></button>
      </div>}
    </>;
}

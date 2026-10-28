import { useEffect, useState } from "react";
import { Download } from "lucide-react";

type InstallChoice = { outcome: "accepted" | "dismissed"; platform?: string };
interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<InstallChoice>;
}

declare global {
  interface WindowEventMap {
    beforeinstallprompt: InstallPromptEvent;
  }
}

export default function InstallPrompt() {
  const [installEvent,setInstallEvent]=useState<InstallPromptEvent|null>(null);
  const [installed,setInstalled]=useState(false);
  useEffect(()=>{
    const onPrompt=(event:InstallPromptEvent)=>{
      event.preventDefault();
      setInstallEvent(event);
    };
    const onInstalled=()=>{setInstalled(true);setInstallEvent(null);};
    window.addEventListener("beforeinstallprompt",onPrompt);
    window.addEventListener("appinstalled",onInstalled);
    return ()=>{window.removeEventListener("beforeinstallprompt",onPrompt);window.removeEventListener("appinstalled",onInstalled);};
  },[]);
  if(installed||!installEvent)return null;
  return <button className="install-button" onClick={async()=>{
    await installEvent.prompt();
    const choice=await installEvent.userChoice;
    if(choice.outcome==="accepted")setInstallEvent(null);
  }}><Download size={14}/> Install app</button>;
}

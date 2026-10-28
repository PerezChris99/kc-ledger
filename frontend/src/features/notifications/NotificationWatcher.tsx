import { useEffect, useState } from "react";
import { X, BellRing } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { playSound, type SoundKind } from "../../sounds";

type Preferences = {notifications_enabled:boolean;sounds:Record<string,boolean>};
type LedgerNotice = {id:number;kind:string;title:string;detail:string;category:string;polarity:number;occurred_at:string};
type NotificationResponse = {items:LedgerNotice[];server_time:string};

function soundFor(item:LedgerNotice):SoundKind {
  if(item.kind.includes("broken")||item.kind.includes("overdue")) return "alarm";
  if(item.kind.includes("at_risk")||item.kind.includes("due_reminder")) return "warning";
  if(item.polarity>0||item.kind.includes("perfect")) return "success";
  return "info";
}

export default function NotificationWatcher() {
  const [notices,setNotices]=useState<LedgerNotice[]>([]);
  const preferences=useQuery({queryKey:["settings"],queryFn:()=>api<Preferences>("/api/settings")});
  useEffect(()=>{
    if(!preferences.data) return;
    let alive=true;
    let cursor=new Date().toISOString();
    const poll=async()=>{
      try {
        const result=await api<NotificationResponse>(`/api/notifications?since=${encodeURIComponent(cursor)}`);
        if(!alive) return;
        cursor=result.server_time;
        if(!result.items.length) return;
        setNotices(previous=>[...result.items,...previous].slice(0,4));
        for(const item of result.items){
          const kind=soundFor(item);
          playSound(kind,Boolean(preferences.data?.sounds?.[kind]));
          if(preferences.data?.notifications_enabled&&"Notification" in window&&Notification.permission==="granted"&&document.visibilityState!=="visible"){
            try { new Notification(item.title,{body:item.detail,tag:`kc-ledger-${item.id}`}); } catch { /* Notifications are optional. */ }
          }
        }
      } catch {
        // Polling failures are non-fatal; the dashboard remains usable.
      }
    };
    const timer=window.setInterval(()=>{void poll();},30000);
    return ()=>{alive=false;window.clearInterval(timer);};
  },[preferences.data]);
  if(!notices.length) return null;
  return <div className="notification-stack" aria-live="polite">{notices.map(item=><article className="notification-toast" key={item.id}><span className="notification-toast-icon"><BellRing size={15}/></span><div><strong>{item.title}</strong><p>{item.detail}</p><time>{new Date(item.occurred_at).toLocaleTimeString()}</time></div><button aria-label="Dismiss notification" onClick={()=>setNotices(current=>current.filter(n=>n.id!==item.id))}><X size={14}/></button></article>)}</div>;
}

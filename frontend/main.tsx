import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./src/App";
import "./src/styles/globals.css";
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, gcTime: 300_000, retry: 1, refetchOnWindowFocus: false } },
});
createRoot(document.getElementById("root")!).render(
  <React.StrictMode><QueryClientProvider client={queryClient}><App /></QueryClientProvider></React.StrictMode>,
);

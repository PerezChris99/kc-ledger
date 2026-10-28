import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [],
      manifest: {
        name: "KC Ledger",
        short_name: "KC Ledger",
        description: "Private financial operations console",
        theme_color: "#0B0F14",
        background_color: "#0B0F14",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }
        ]
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,woff2}"],
        navigateFallback: "/index.html",
        runtimeCaching: []
      }
    })
  ],
  build: { outDir: "dist", emptyOutDir: true },
  server: { host: "0.0.0.0", port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } }
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Never persist authenticated financial API responses in a service-worker cache.
// Static assets are revisioned and the app shell can load offline; business
// records, session checks and mutations always require the live Django API.
export default defineConfig({
    plugins: [
        react(),
        VitePWA({
            registerType: "prompt",
            strategies: "generateSW",
            injectRegister: null, // managed by virtual:pwa-register/react
            includeAssets: [
                "icon.svg",
                "pwa/favicon-32.png",
                "pwa/apple-touch-icon.png",
                "pwa/icon-192.png",
                "pwa/icon-512.png",
                "pwa/maskable-512.png"
            ],
            manifest: {
                id: "/",
                name: "KC Ledger — Financial Operations",
                short_name: "KC Ledger",
                description: "Private, installable business and financial operations console.",
                categories: ["business", "finance", "productivity"],
                lang: "en",
                start_url: "/",
                scope: "/",
                display: "standalone",
                orientation: "any",
                theme_color: "#0B1B3D",
                background_color: "#F5F5F7",
                icons: [
                    { src: "/pwa/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
                    { src: "/pwa/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
                    { src: "/pwa/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
                ],
            },
            workbox: {
                globPatterns: ["**/*.{js,css,html,svg,png,woff2,webmanifest}"],
                maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
                cleanupOutdatedCaches: true,
                clientsClaim: true,
                skipWaiting: false,
                navigateFallback: "/index.html",
                navigateFallbackDenylist: [
                    /^\/api(?:\/|$)/,
                    /^\/admin(?:\/|$)/,
                    /^\/downloads(?:\/|$)/,
                    /^\/static(?:\/|$)/,
                    /^\/health(?:\/|$)/,
                    /^\/pwa(?:\/|$)/,
                    /^\/assets(?:\/|$)/,
                    /^\/sw\.js$/,
                    /^\/workbox-.*$/
                ],
                runtimeCaching: [
                    {
                        urlPattern: ({ url }) => (
                            url.origin === self.location.origin
                            && (/^\/(api|admin|downloads|static)(\/|$)/.test(url.pathname))
                        ),
                        handler: "NetworkOnly",
                        method: "GET",
                    }
                ],
                // Do not add network-first caching to API, auth, invoice, export,
                // events or other user-specific endpoints. No offline mutation queue.
            },
        })
    ],
    build: { outDir: "dist", emptyOutDir: true },
    server: {
        host: "0.0.0.0",
        port: 5173,
        proxy: { "/api": "http://127.0.0.1:8000" }
    }
});

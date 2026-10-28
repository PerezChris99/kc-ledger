# Progressive Web App

Vite's PWA plugin generates the manifest and Workbox service worker. Static application assets are precached; API requests and financial responses are not cached. An install prompt is shown only when the browser emits `beforeinstallprompt`. The interface respects reduced-motion preferences. Offline use is limited to the cached app shell; data actions require a reachable backend.

## Changelog
- 2026-10-28: Added the manifest, asset-only service worker and install prompt.

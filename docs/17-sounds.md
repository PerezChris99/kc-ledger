# Sounds and notifications

The browser synthesizes short tones through Web Audio for success, info, warning and alarm categories. No audio files or audio network requests are required. Sound toggles and browser-notification preferences are stored in the server's Meta settings record. The user explicitly requests notification permission from Settings; desktop notifications are shown only when permission is granted and the app is in the background. In-app notices are displayed when new reminder or verdict events arrive.

## Changelog
- 2026-10-28: Added synthesized tones, event polling and configurable notification preferences.

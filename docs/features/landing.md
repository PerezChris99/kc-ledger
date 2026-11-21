# Sign-in and private access

The implemented unauthenticated entry point is a **KC light-themed private owner sign-in**, not a public marketing landing page. The real component is [LoginPage.jsx](../../frontend/src/features/auth/LoginPage.jsx), rendered by the authenticated [App.jsx](../../frontend/src/App.jsx) flow.

The entry screen includes a private brand message, username/password form, request feedback and a restricted access indication. Django supplies the authenticated session; CSRF protection applies to sign-in and unsafe requests. A first owner is created from configured environment variables in the Docker route or by an on-device setup dialog in the Windows route.

**Original spec difference:** the 28 October master spec proposed a stock-photo slideshow and dark terminal layout. That is **not implemented**, and the merged light-paper redesign is the current product direction. Do not represent the proposed slideshow as a completed feature or a mandatory release blocker unless the owner explicitly reinstates it.

Release checks: correct autofill and password masking, no credential leakage in logs, visible errors on failed or throttled login, accessible labels, logout/session expiry, and responsive layout at 375px and desktop widths.

_Updated 2026-11-15._

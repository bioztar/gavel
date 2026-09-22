# Distributing the extension

`packages/extension` is the "Chair this meeting" button in Google Calendar and
Google Meet. It reaches users through one of two doors, and the manifest is
written so that the second door stays open.

## Door 1 — self-serve: Chrome Web Store, Edge Add-ons

The user installs it themselves.

- **Chrome Web Store**: one-time developer registration, upload the `dist/` zip
  (`npm run build`, then zip the folder — nothing else goes in), fill in the
  listing and the privacy tab, submit for review. Reviews for extensions with
  `identity` and a Google OAuth scope take days, not hours; every added
  permission triggers a re-review. Unlisted visibility is fine for a pilot.
- **Edge Add-ons**: same package. Edge runs MV3 extensions and
  `chrome.identity.launchWebAuthFlow`; `getAuthToken` is not available there,
  which is why the extension falls back to the web-auth flow automatically.
  Edge's store also accepts a Chrome Web Store listing as the source.
- Firefox is not a target yet: no `identity.getAuthToken`, different
  `browser_specific_settings`, and `chrome.storage.session` arrived late. The
  code path is `launchWebAuthFlow` + `storage.session`, so it is a packaging
  job later, not a rewrite.

The OAuth client for this door is a Google Cloud OAuth client of type *Chrome
Extension* bound to the store item id; the id is baked into `manifest.oauth2`
at build time (`GAVEL_GOOGLE_CLIENT_ID`). Only the client **id** ships; there
is no client secret in this flow at all. Google's OAuth verification for the
`calendar.events.owned` scope (a "sensitive" scope) is a separate review of the
Cloud project: privacy policy URL, a demo video, and the consent-screen text.
Start it early: until it is done the consent screen carries an "unverified
app" warning and Google caps how many users can grant the scope.

## Door 2 — admin-deployed: Google Workspace Marketplace

A Workspace admin installs gavel for the whole organization. This is two
pieces, because the Marketplace does not list browser extensions as an
integration type — its app integrations are Workspace add-ons, Editor add-ons,
Drive apps, Chat apps, Classroom add-ons and **web apps**
(developers.google.com/workspace/marketplace/overview):

1. **Marketplace listing = the `packages/calendar` deployment as a *Web app*.**
   The listing carries the OAuth scopes; when the admin installs it
   domain-wide they grant those scopes once for everyone, so no user sees a
   consent screen. The listing needs the web app's universal-nav URL, a
   privacy policy, terms and a support contact, and the app must be in
   production. Visibility can be *Private* (our domain only) for a pilot —
   note the SDK's warning that public/private is permanent once chosen.
2. **The extension is pushed by Chrome enterprise policy**, from the Chrome Web
   Store item published in Door 1 (Admin console → Chrome browser → Apps &
   extensions → force-install; the same thing as `ExtensionInstallForcelist`
   for browsers managed by other MDMs). Admins can also pin which sites it may
   run on and pre-seed its settings there.

What that route requires that Door 1 does not:

- The **Google Workspace Marketplace SDK** enabled in the same Cloud project as
  the OAuth client, with the OAuth scopes listed there **matching exactly** the
  scopes the extension requests. A runtime scope that is not declared on the
  listing is not covered by the domain-wide grant, and the user is prompted or
  refused.
- OAuth verification for the sensitive scope must be complete first.
- One server origin per deployment, or an admin-settable one. Today the origin
  is a `chrome.storage.local` setting on the options page; for admin rollout we
  add a `storage.managed_schema` so the Admin console's extension policy can
  set it. That is additive and changes no permission.

## Manifest and permission choices that would block Door 2 — and what we chose

| Would block or slow the Marketplace / admin route | What `packages/extension` does |
| --- | --- |
| `<all_urls>` or `*://*/*` in `matches` or `host_permissions` — flagged as broad host access, requires justification, and admins can refuse it wholesale | Content scripts match `https://calendar.google.com/*` and `https://meet.google.com/*` only; `host_permissions` is empty. The dev build adds `http://localhost:8790/*` and that is stripped from `dist/`. |
| Broad Google scopes (`calendar`, `calendar.readonly`, `calendar.events` across all calendars, Directory) — "restricted" or org-wide scopes need a security assessment | `calendar.events.owned` (events the user owns) + `userinfo.email`. Nothing read-all, nothing org-wide. |
| Remote code — CDN scripts, `eval`, `new Function`, `importScripts` of remote URLs — MV3 forbids it and the store rejects it | Everything is bundled by esbuild from `src/`; `scripts/audit-bundle.mjs` fails the build if any of those appear. CSP is `script-src 'self'; object-src 'none'`. |
| Any client secret, API key or provider credential in the bundle — an instant rejection and a leaked key | None. The only build-time input is the public OAuth client id. The audit also greps for credential-shaped literals. |
| Requesting `identity.email` or `tabs`/`webNavigation`/`history` for convenience | `permissions` is `["identity", "storage"]`. The email comes from the scoped `userinfo.email` grant, not from a browser permission. |
| `localStorage` or `chrome.storage.local` for tokens — fails the data-handling questionnaire | Tokens are in `chrome.storage.session` (memory, cleared on browser close). `storage.local` holds the server origin and a dev flag. |
| Consent-screen scopes that differ between the manifest, the Cloud OAuth client and the Marketplace SDK | One list in `manifest.oauth2.scopes`; the build does not mutate it. Keep the Cloud project's OAuth client and Marketplace SDK entries copied from there. |
| Changing the extension id (a new key) after admins have force-installed it, or after the OAuth client was bound to it | Publish once, keep the same store item; the OAuth client of type *Chrome Extension* is bound to that id. Unpacked dev builds have a different id and are never what admins install. |

Two things to do before Door 2, both outside this repo: complete OAuth
verification for `calendar.events.owned`, and decide whether the server origin
is fixed per deployment (bake it into the build) or admin-configured (add a
`storage.managed_schema`). Neither changes the permission surface above.

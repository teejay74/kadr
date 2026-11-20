# Source search deadline and error reporting — 2026-11-20

## Completed work

Reproduced the MobLand (247718) season-2 request from the user's screenshot.
Metadata returned HTTP 200, while source search returned `indexer_unavailable`.
Existing nginx 504 responses were mapped to the misleading generic catalogue
message. Added a configurable total 25-second source-search/resolution deadline
(including metadata and every query variant), cancellation of in-flight work,
and explicit source-deadline / gateway messages in the shared web API service.

## Changed files

Backend source service/dependencies/config and source tests; Compose and
`.env.example`; shared frontend API/error tests; deployment, API and
troubleshooting documentation. No network, router, tracker or VPN settings changed.

## Checks and results

- 194 backend tests passed; new regression verifies slow provider cancellation.
- 112 frontend tests passed; gateway and source-deadline messages covered.
- Ruff, strict TypeScript and production frontend build passed.
- Server preflight: clean checkout, all five KADR services healthy, about 5.5 GiB
  available RAM, 103 GiB root free, retained online database backups inspected.
- Deployment and live deadline validation recorded after rollout below.

## Known issues and next actions

This patch improves bounded execution and reports the actual error; it does not
claim to restore access to unreachable trackers. Previous diagnostics found
tracker DNS redirection and a TLS timeout even with independent DNS. A usable
network route/proxy for Prowlarr remains necessary; user input about an existing
connection has been requested. No fake source results or progress were added.

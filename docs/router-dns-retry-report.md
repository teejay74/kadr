# Tracker DNS retries and IPv4-only trial — 2026-11-20

## Completed work

Applied the explicitly approved resolver options `timeout:2 attempts:5` to
Prowlarr and FlareSolverr, retaining DNS `192.168.1.1`. Enabled the documented
.NET `DOTNET_SYSTEM_NET_DISABLEIPV6=1` switch only for Prowlarr. These values
remain active in the deployment environment. Recreated only the two approved
tracker containers; no host/router/Photodom network settings changed.

## Changed files and backups

- `docker-compose.router-dns.yml`: scoped resolver options and optional runtime
  switch controlled by KADR environment values.
- `.env.example`, `docs/deployment.md`: settings and rollback guidance.
- Private server `.env`: DNS timeout 2, attempts 5, Prowlarr IPv6 switch 1.
- Private environment and verified online Prowlarr database backups retained
  under `/srv/kadr/backups`, timestamp `20261120-183229`.

## Checks and test results — FAILED stability acceptance

- Compose syntax and structural comparison passed: only DNS options on the two
  containers and the Prowlarr-specific environment switch differ from base.
- Docker inspection and container environment/resolv.conf confirmed the values.
- RuTor indexer test: HTTP 200.
- Five consecutive KADR web-entry requests for series 247718, season 2, RuTor:
  1. HTTP 200, 2 sources, 2.12 s.
  2. HTTP 200, 2 sources, 2.26 s.
  3. HTTP 200, 2 sources, 0.64 s.
  4. HTTP 502, 3.52 s; Prowlarr rejected the search.
  5. HTTP 502, 0.03 s; Prowlarr temporary indexer backoff was active.
- A subsequent selected-indexer movie search also returned 502. The all-indexer
  request returned HTTP 200 with zero sources; this is not recovery evidence.
- New Prowlarr logs again reported SocketException (11), Resource temporarily
  unavailable (rutor.is:443), during name resolution. The approved tuning did
  not eliminate the fault and is not presented as a successful repair.

## Further read-only diagnostics

Direct DNS requests to the router intermittently timed out for A and AAAA. In
three UDP rounds, one A and one AAAA lookup timed out; successful A lookups
returned an address, successful AAAA lookups returned NOERROR with no answers.
A separate TCP A lookup succeeded while TCP AAAA timed out. Short diagnostic
timeouts establish variability, not a definitive internal router failure cause.

The existing browser AWG Manager DNS information page showed upstream DoT
servers 1.1.1.1 and 8.8.8.8. Settings were only read. The primary Keenetic web
configuration page requires sign-in, so deeper router configuration inspection
remains pending. No settings were saved or toggled on either router interface.

## Known issues and next actions

Stable search remains unresolved. Further router DNS diagnostics are needed;
any router configuration change requires separate explicit approval. Keep the
rollback backups and do not claim stability from one successful indexer test.

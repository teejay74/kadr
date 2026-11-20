# Router DNS recovery for tracker search — 2026-11-20

## Completed work

After explicit user approval, configured only KADR Prowlarr and FlareSolverr
containers to use router DNS `192.168.1.1` through an optional Compose override.
The router already has domain-based VPN routing configured by the user.
The server deployment `.env` retains both COMPOSE_FILE and KADR_ROUTER_DNS so
subsequent Compose operations preserve this setting. No Debian/Tailscale DNS,
Keenetic configuration, Photodom, API, web or qBittorrent settings were changed.

## Confirmed cause and evidence

The Prowlarr container resolved `rutor.is` to `78.29.1.40` and timed out. Router
DNS returned `193.46.255.26`. A diagnostic HTTPS GET from that same container,
with the router's answer and correct TLS hostname, returned HTTP 200. After the
DNS override and container recreation, Prowlarr resolved the correct address
on its own and an ordinary HTTPS GET returned HTTP 200. No CDN/tracker IP was
pinned in deployment configuration, and certificate verification stayed enabled.

## Changed files and deployment state

- `docker-compose.router-dns.yml`: DNS override for exactly two services.
- `.env.example`: commented opt-in settings.
- `docs/deployment.md`: enablement, validation and rollback instructions.
- Private server `.env`: persisted approved override selection and router DNS.
- Private `.env` copy and verified online Prowlarr database backup created before
  rollout, with timestamp `20261120-182337` under `/srv/kadr/backups`.
- Only Prowlarr and FlareSolverr were recreated; image versions were unchanged.

## Checks and results

- Compose configuration passed. A structural comparison with base Compose proved
  the only service changes were the DNS values on Prowlarr and FlareSolverr.
- Docker inspection confirmed DNS `["192.168.1.1"]` on both containers.
- Prowlarr RuTor indexer test returned HTTP 200.
- Through the public KADR web entry point:
  - Movie 299534, RuTor: HTTP 200, 68 real sources, 3.81 seconds.
  - Series 247718 season 2, RuTor: HTTP 200, 9 real sources, 10.86 seconds;
    sample releases explicitly contained S02E01–09.
  - Series 247718 season 2, all sources: HTTP 200, 2 real sources, 2.23 seconds.
- No application code changed; this validation targets actual DNS, HTTPS,
  integration health and real source search rather than repeating unit tests.

## Known issues and next actions

Other individual indexers were not all retested. Prowlarr's pre-existing
backoff and individual tracker availability may still affect their results.
If failures recur, inspect router DNS availability, domain-policy coverage and
Prowlarr health. Source counts vary with provider results and search variants;
these observations do not guarantee continuous availability of every tracker.

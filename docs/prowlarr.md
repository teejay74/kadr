# Prowlarr setup

Prowlarr is KADR's internal indexer manager. Stage 3 uses it only for interactive
search; no download client should be configured yet.

## Local setup

1. Start it with `docker compose up -d prowlarr`.
2. Open `http://127.0.0.1:9696` on the KADR host.
3. Complete the initial authentication setup. Use a unique password.
4. Open Indexers, select `+`, and configure a torrent indexer you are authorized
   to access. Use Prowlarr's Test action before saving.
5. Open Settings → General and copy the API Key into the ignored `.env` as
   `KADR_PROWLARR_API_KEY`.
6. Apply it with `docker compose up -d --force-recreate api`.
7. Verify `http://localhost:8180/api/v1/indexers` and then use “Найти источники”
   on a KADR media page.

Do not configure qBittorrent or another download client in this stage. Do not
publish port 9696 to the LAN or internet. On a remote host, keep the loopback
binding and use an SSH tunnel for administration.

KADR does not ship indexer definitions, accounts, cookies, or credentials.
Availability and permitted use depend on each indexer's rules and jurisdiction.

## Cloudflare-protected indexers

KADR runs FlareSolverr only on the internal Compose network. In Prowlarr, open
Settings → Indexers → Indexer Proxies, add a FlareSolverr proxy with host
`http://flaresolverr:8191`, and give it a dedicated tag such as
`flaresolverr`. Add the same tag to each indexer that needs it. An empty tag
does not enable the proxy, and mismatched tags do not route requests through
it.

FlareSolverr is invoked only when Prowlarr detects Cloudflare. It can handle
supported browser challenges but cannot bypass a hard block on the server's
public IP. Do not expose port 8191, raise concurrency without measuring RAM, or
route private trackers through a VPN/proxy that violates their rules.

Prowlarr validates this proxy against `prowlarr.servarr.com`. If that host is
blocked for the server IP, the proxy's Test action can fail even when the
target indexer challenge is solved. Confirm the target indexer separately and
check FlareSolverr without enabling request-body logging.

RuTor reports its releases in Prowlarr's `Other` category rather than reliable
movie/TV subcategories. KADR includes category `8000` alongside the requested
movie or TV category and still applies a media-title query. Localized metadata
titles are searched first, with the original title used only as an empty-result
fallback.

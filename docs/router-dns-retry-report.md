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

After the user signed in, read-only inspection confirmed AWG Manager 2.19.2,
HydraRoute Neo running, and KeeneticOS 5.02.B.3.0-2 on Hopper KN-3810. Routing
is managed through AWG Manager / HR Neo; the server's default access policy
alone does not establish missing VPN routing. Do not move the entire shared
server onto a VPN policy.

Router DNS uses encrypted upstreams 1.1.1.1 and 8.8.8.8 alongside configured
plain DNS entries. DNS timeouts also reproduced directly on Debian outside
Docker. Direct TLS connections from Debian to both encrypted upstreams worked;
this does not establish the health of the router's own upstream connections.

The native Keenetic system log showed repeated messages around 18:49:

- `ndnproxy: FQDN mirroring failed "Resource temporarily unavailable".`
- `ndnproxy: FQDN reply mirroring failed "Resource temporarily unavailable".`
- `Core::Executive::EventLoop: "Dns::Route::EventSink::default": poll timer: too long delay.`

These establish router-side DNS mirroring errors, but do not prove HR Neo,
upstream DNS, or firmware as the root cause. The AWG Manager journal also
recorded two earlier temporary failed monitoring probes for the reserve tunnel;
no causal connection to the failed search was established. No router network
settings were changed, services restarted, or firmware updated.

Primary reports of similar symptoms on earlier KeeneticOS 5.2 builds are at
[Keenetic Community](https://forum.keenetic.ru/topic/30978-52-a11-dnsrouteeventsink-%E2%80%94-%D1%80%D0%BE%D1%81%D1%82-timeoutshangs-%D0%B8-poll-timer-too-long-delay/).
Those reports are observations, not a confirmed vendor diagnosis or fix.

## Approved router reboot verification

The user explicitly approved one router reboot, performed through Keenetic's
normal reboot control around 19:05 local time on 2026-11-20. The user confirmed
completion. SSH access to Debian returned; all five KADR containers remained
healthy without recreation. No configuration or firmware was changed.

After reboot, ten direct router DNS lookups from the API container (five A and
five AAAA for rutor.is) completed without timeout: A returned one answer in
0–0.25 s; AAAA returned NOERROR with zero answers in 0.30–0.45 s. RuTor's
Prowlarr indexer test returned HTTP 200. Five consecutive searches through the
actual web entry point, for series 247718 season 2 with indexer_id=1, all returned
HTTP 200 with two sources, in 1.35, 1.32, 1.99, 2.07 and 1.87 seconds.

The immediate verification passes, whereas the same trial failed before reboot.
This supports accumulated router state as a contributing factor but does not
establish the precise cause or durable recovery. Router authentication expired
after reboot, so the native post-reboot system journal was not read.

## Remaining limitations

Long-term stability remains unverified. If the error returns, capture the router
DNS mirroring log and Prowlarr errors before another intervention. Router changes
beyond the completed single reboot require separate approval. Keep the rollback
backups; do not treat this short successful trial as a permanent firmware fix.

## All-indexer result after reboot

A subsequent live KADR search for series 247718, season 2, with no indexer
selection returned HTTP 200 and two releases, both from RuTor. Prowlarr listed
five configured, enabled indexers, but its status endpoint showed temporary
failure backoff for Kinozal (M), NoNaMe Club, RuTracker.org, and BigFANGroup.
Thus the two releases are not evidence of a complete search across five
indexers. When their backoff ends, they can be retried; another upstream failure
can disable them again. Also, the current KADR season search returns on the
first title/query variant that yields matching results, which can limit the
release set independently of indexer availability. Further repair and repeated
all-indexer verification remain open.

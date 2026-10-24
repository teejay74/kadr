# qBittorrent setup

qBittorrent is KADR's Stage 4 download engine. KADR talks to its Web API over
the private Compose network; the browser never receives its password, torrent
URI, or hash. Its administrative UI is available only from the same machine at
<http://127.0.0.1:8081>.

## Initial setup

1. Run `docker compose up -d qbittorrent`.
2. Read only the initial qBittorrent startup log and locate the temporary Web UI
   password: `docker compose logs --tail=100 qbittorrent`.
3. Sign in at `http://127.0.0.1:8081` as `admin` with that temporary password.
4. In Tools → Options → Web UI, set a unique username and a long password.
5. Put the same values in the ignored `.env` file as
   `KADR_QBITTORRENT_USERNAME` and `KADR_QBITTORRENT_PASSWORD`.
6. Recreate the API: `docker compose up -d --build api web`.

Do not commit `.env`, publish port 8081 to the LAN, disable qBittorrent
authentication, or enable hostname/CSRF bypasses. KADR uses the internal
address `http://qbittorrent:8080`; the host port is only for local setup.

## KADR behavior

- A source uses qBittorrent's `MetadataReceived` stop condition. A magnet may
  briefly show `metaDL`, then stops before content download.
- The user chooses one supported video; all other torrent files receive
  priority zero and that video receives high priority.
- Starting is blocked until a selection exists, the active-torrent limit is
  available, and the configured free-space floor is satisfied.
- Stop never deletes the torrent or its files.
- Progress is read from qBittorrent on demand; the UI does not poll rapidly.

Use only content you are authorized to download. Torrent streaming and cache
deletion are later stages and are deliberately absent here.

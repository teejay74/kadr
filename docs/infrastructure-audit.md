# Infrastructure audit (local preparation host)

Date: 2026-10-23 (Asia/Yekaterinburg).

The repository was prepared on macOS ARM64, not on the target Debian server.
Docker 28.0.4 and Docker Compose 5.5.0 are available. Host ports 5000, 7000,
8081, 8222, 8443 and several loopback application ports were occupied; 8180
was not observed as listening and is the Stage 1 default. The local filesystem
had about 65 GiB free during the audit. Host Node.js was absent and host Python
was 3.9.6, so reproducible pinned container toolchains are used.

No disks, mounts, containers, networks, remote hosts, or Photodom files were
modified. This is not a Debian deployment approval. Complete the read-only
preflight in `docs/deployment.md` on the actual server before deployment.


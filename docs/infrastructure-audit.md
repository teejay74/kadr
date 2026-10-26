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

## Debian deployment host

Date: 2026-10-26 (Asia/Yekaterinburg).

The target host is Debian 13.7 (`x86_64`) with Docker Engine 26.1.5 and Docker
Compose 2.26.1. Before deployment, the host had one running Compose project,
`photo-web-v3`, publishing port 8080. Ports 80, 8180, 9696, and 8081 were not
published on LAN interfaces. The host had 7.7 GiB RAM, 8 GiB swap, negligible
load, and about 111 GiB free on the 226 GiB ext4 root filesystem. The intended
`/srv/kadr` path did not exist.

The 2 TB Samsung SSD is `/dev/sda`. Its only partition, `/dev/sda1`, already
occupies the disk and is mounted as ext4 at `/srv/photo-storage`, with about
1.6 TB free during the audit. No partition, filesystem, mount, firewall rule,
Photodom path, or Photodom container was changed. Shrinking that live ext4
filesystem to create another partition is not an acceptable deployment action.
If KADR storage is later placed on this disk, use a separately owned KADR
directory and bind mount only after explicit approval and a verified backup;
do not repartition the Photodom disk.

The user subsequently approved that non-partitioning approach. KADR persistent
data was copied to the separately owned `/srv/photo-storage/kadr` directory,
verified against the source, and selected through `KADR_DATA_ROOT`. The
original `/srv/kadr/data` tree was retained as a rollback copy. The existing
partition and mount were not changed.


# Streaming

Streaming is explicitly out of scope through Stage 2. There is no player, HTTP
Range endpoint, torrent client, fake download, or transcoding process in this
repository.

Stage 5 must implement and test byte-range semantics, availability-aware reads,
timeouts, seeking, disconnects, concurrent sessions, and cleanup. Direct Play
is the priority. Remux is conditional; transcoding remains reserved and must
never start automatically.


# MQTT transport: TLS by default and signed commands

Status: plan (not implemented). Add-on 2.2.1 only warns at start-up when `mqtt_tls` is off.

## Why

Today the add-on defaults to `mqtt_tls: false` on port 1883. On that path the MQTT password,
telemetry and the vault's commands travel in clear text, and anyone who can reach the broker (or sit
on the path) can read them or publish `hubs/<id>/v1/cmd/...` as the vault. The hub's own checks
(retained, repeated, stale and oversized commands are refused; `registry/set` needs a token; the hub
never writes state to Home Assistant) limit the damage but do not prove who sent a command.

Two separate gaps:

1. **Transport**: no encryption or broker authentication by default.
2. **Origin**: even over TLS the broker is the only thing between a hub and anyone else holding
   broker credentials. Commands are not signed, so a leaked credential or a mis-scoped ACL lets
   another client command a hub.

## What exists already

- Vault: its own CA (`app/cert_provisioner.py`), a client certificate per hub (CN = hub id),
  stored encrypted in `mqtt_hubs`; `GET /hubs/<id>/download-config` returns broker, port 8883,
  `tls: true`, the CA and the hub's certificate and key.
- Broker: `mosquitto-mtls.conf` listens on 8883 with `require_certificate true` and
  `use_identity_as_username true`; a 1883 listener bound to 127.0.0.1 for the vault itself.
- Add-on: `mqtt_tls` and `mqtt_cert_bundle` options; with TLS on, a failed TLS set-up refuses to
  connect (no plaintext fallback, since 2.1.0); `client_id` defaults to the certificate CN.
- Commands carry `command_id`, `action`, `payload` and an ISO UTC `timestamp`.

## Part 1: TLS by default with the vault's CA and per-hub credentials

### Vault and broker

1. Production broker: only the mTLS listener (8883) is reachable from outside; 1883 stays bound to
   127.0.0.1 for the vault. Drop `allow_anonymous` on any external listener.
2. Fix the ACL: `acl.conf` has `pattern read hubs/%u/cmd/#` but the topics are
   `hubs/<id>/v1/cmd/...`. Use, with `%u` = certificate CN:
   - `pattern read hubs/%u/v1/cmd/#`
   - `pattern write hubs/%u/v1/ack/#`, `pattern write hubs/%u/v1/telemetry/#`, and the status/LWT topic.
   - No hub can read or write another hub's topics. Only the vault user may write `.../cmd/#`.
3. `download-config` returns the bundle in the exact shape the add-on's `mqtt_cert_bundle` accepts,
   so a hub owner pastes one value. Certificates last 1-2 years; before expiry the vault re-issues
   one and the owner re-downloads it (a later `config/rotate_cert` command, signed as in Part 2, can
   deliver it over the existing mTLS session).
4. Revocation: `revoke_certificate` feeds a CRL that mosquitto loads (`crlfile`), and the hub row is
   marked revoked so the vault stops commanding it.
5. Keep the CA private key out of the repository (it is currently next to `init-ca.sh`); load it
   from the secret store.

### Add-on

1. 2.2.1 (done): start-up warning naming host:port and this document when TLS is off.
2. Next minor: the add-on UI marks TLS as recommended; `mqtt_cert_bundle` validated at start-up
   (CA present, cert CN equals `client_id`, key matches cert, not expired) with a clear log line.
3. Next major: default `mqtt_tls: true`, port 8883. A hub with TLS off refuses to connect unless the
   owner sets an explicit `mqtt_allow_plaintext: true` (for a broker on the same LAN, for example).

### Migration

- Phase A (now): warn. The vault's hub page shows "TLS off" for hubs whose status arrives on 1883.
- Phase B: vault emails owners of plaintext hubs with the download link; both listeners run.
- Phase C (major release): the add-on default flips. Existing installs keep their saved options,
  so a hub with `mqtt_tls: false` saved keeps working until the owner changes it or the broker drops
  1883. The broker closes the external 1883 listener only when the vault sees no hub on it for
  30 days.

## Part 2: HMAC-signed commands

TLS proves the broker; signing proves the vault. Each hub gets its own key so one leaked hub key
cannot command another hub.

### Key provisioning

- At hub set-up the vault generates a 32-byte random `command_key` per hub, stores it encrypted in
  `mqtt_hubs` (new column `command_key_encrypted`, plus `command_key_id`), and includes it in the
  `download-config` bundle (`"command_key": {"id": "k1", "secret": "<base64>"}`).
- The add-on stores it with the other secrets (password-type option, never logged). Key rotation:
  `config/rotate_command_key` signed with the old key; the hub accepts both keys for 24 h.

### Message format

```json
{"command_id": "...", "action": "sensors/set", "payload": {...},
 "timestamp": "2026-10-01T12:00:00Z", "nonce": "<16 random bytes, base64url>",
 "sig": {"alg": "HMAC-SHA256", "kid": "k1", "value": "<base64url>"}}
```

Signed bytes: `v1\n<hub_id>\n<topic>\n<timestamp>\n<nonce>\n<command_id>\n<canonical JSON of payload>`,
where canonical JSON is `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`.
Binding the hub id and topic stops a signed command for hub A, or for `sensors/poll`, being replayed
to hub B or to `registry/set`.

### Verification on the hub

1. Missing or malformed `sig`: refuse with `failed` / `unsigned_command` (once enforcement is on).
2. Unknown `kid`: `unknown_key`. Bad MAC (`hmac.compare_digest`): `bad_signature`, no other detail.
3. Replay window: `timestamp` within +/-5 minutes of the hub clock (`stale_command` /
   `future_command`); `nonce` not seen in the last 10 minutes (bounded LRU, e.g. 4096 entries,
   cleared on restart, which the timestamp window covers). Today's 10-minute stale check and
   `command_id` dedupe remain.
4. Only then is the command dispatched. Checks run in `_accept_command`, before any handler.

Clock skew: the hub logs its offset from the vault's timestamps; a hub more than 5 minutes off sees
every command refused with `stale_command`, which the vault shows as "hub clock wrong".

### Vault changes

- `MQTTService.publish_command` adds `nonce` and `sig`; `CommandBase` in central-core-mqtt-shared
  gains `timestamp`, `nonce`, `sig` (optional during migration) and a shared `sign()/verify()` helper
  with test vectors so vault and hub cannot disagree on canonicalisation.
- The hub's ACKs echo `command_id`; ACK signing (hub to vault) uses the same key and format and can
  follow later.

### Migration

- Phase 1: vault signs every command; hub with a key verifies and logs failures but still acts
  (`command_signing: log`). Hubs without a key behave as today.
- Phase 2: hub default `command_signing: enforce` when a key is configured; the vault page lists
  hubs without a key with a "re-download configuration" action.
- Phase 3 (major release): unsigned commands are refused by default.

## Tests to add when implementing

- Shared test vectors (payload, key, expected MAC) used by both repositories.
- Hub: valid; bad MAC; wrong hub id; wrong topic; replayed nonce; stale and future timestamps;
  unknown kid; key rotation overlap; log mode does not block; enforce mode refuses before dispatch.
- Add-on start-up: TLS off warning (exists), plaintext refused in the major release unless
  `mqtt_allow_plaintext`.
- Broker ACL: a hub certificate cannot subscribe to another hub's `cmd/#` or publish to any `cmd/#`.

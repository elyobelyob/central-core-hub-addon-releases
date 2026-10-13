# Moving the hub onto its own broker login (add-on 2.4.5)

The vault can move a hub from the shared MQTT login to a login of its own without anyone typing it into Home Assistant. The protocol (messages, crypto, timing, result codes) is in `central-core-mqtt-shared`, `docs/LOGIN_CHANGE.md`. This page is about what the add-on does.

## What happens

1. `cmd/login/key_request`: the hub makes a one-use key, keeps it in memory only, and answers with the public half, a request id and a short fingerprint. It writes the fingerprint to its log so the owner can compare it with the one the vault shows. The key expires after 10 minutes.
2. `cmd/login/change`: the hub decrypts the new username and password (the hub id and request id must match, or it does not decrypt), then tests the new login on a second MQTT connection: same broker, same TLS, a different client id. The test connects, subscribes to the hub's own command topic and store acknowledgement topic, and publishes one message to a probe topic. The broker's answers must all be success (the test uses MQTT 5 so a refusal is visible).
3. Only if the test passes is the new login saved and the main connection switched to it. The hub is then given 2 minutes to connect. If the broker refuses it, or the connection is not up in time, the hub goes back to the old login, saves that again, and reports `rolled_back`.
4. The hub reports `ok` or the failure reason with the username in use, never the password. The report carries an HMAC `confirmation` that only the real hub and the vault can make.

A wrong key, a reused request id, a message for another hub or a login that fails the test change nothing. A bad message does not use up the key; a good one does.

## How the login is saved

In `/data/login_override.json` (mode 0600, written atomically). At start-up the hub uses it instead of the login in `options.json`; the start-up log line says which, for example `MQTT login: 'hub-example' (from override)`, and never shows the password.

The Supervisor would let the add-on rewrite its own options (`POST /addons/self/options` works for an add-on's own options whatever its API role, so `hassio_api` is not needed). It is not used: the call must send every option, so it can undo an edit the owner has made but not yet restarted for, and `options.json` is only refreshed when the add-on restarts, so the two copies would disagree for a while. The price is that the Home Assistant screen keeps showing the old login.

To go back to the login in the options by hand: turn on `reset_saved_login` in the add-on options and restart. The hub deletes the override and any unconfirmed-move record, and says so in its log. Turn the option off again afterwards.

While a move is unconfirmed there is also `/data/login_pending.json` (the new and the old login, and the move's ids). It is removed as soon as one of the two logins has connected. If the add-on stops mid-move, the next start waits up to 2 minutes for the login it is on to connect, then tries the other, and keeps whichever connects. If neither does (the broker may be down), the record stays for the next start.

## Rules the add-on keeps

- Only `hub-<hub id>`, `hub-<hub id>-a` and `hub-<hub id>-b` are accepted as usernames.
- It will not send a password over a connection with MQTT TLS off (`tls_required`).
- The one-use key is used up only when the new login has passed the test and is about to be saved. A message that does not decrypt, names a wrong login, or fails the test leaves the key for the vault's real message. Up to four keys can be waiting at once, and a message that decrypts holds the hub busy while its login is tested (up to 30 seconds), so someone who can publish on the hub's topics can still delay a move (the vault retries); they cannot make it use a wrong login.
- It will not take a move while `reset_saved_login` is on, since the next restart would delete what the move saved.
- If neither login connects, it keeps alternating between them (waiting longer each time, at least 15 seconds per try) until one does or the add-on stops, and keeps the unconfirmed record. If a login could not be written to disk before it was tried, the hub stays online on it but reports nothing until the next start has settled the record.
- It reports `ok` only if the main connection is up on the new login; if it ends up on the old one it reports `rolled_back`, and a restart that finds the hub on a login that is not the new one never reports `ok`.
- Results sent before the login was decrypted (bad request, unknown or expired key, and so on) carry no confirmation code. The vault treats them as advice only. The vault's own rules are in `central-core-mqtt-shared`, `docs/LOGIN_CHANGE.md`.

## Not in this version

- The login in use is not part of the regular status payload; the result of the move is the only report.
- No "undo" command. Move the hub again from the vault, or use `reset_saved_login`.
- A forged `login/change` that decrypts (anyone can encrypt to the hub's public key) lets someone guess passwords for the hub's own `hub-<id>`, `-a` and `-b` logins through the hub's login test; they need to be able to publish commands to do so, which is already full control. Vault rule: do not create hub ids that end in `-a` or `-b`, because `hub-X-a` would then be both a slot of hub `X` and the login of hub `X-a`.
- The vault is not authenticated to the hub, and the hub's key is not authenticated to the vault; the owner compares the key fingerprint by eye, and the rules above limit what a forged message can do.

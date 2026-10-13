# Changelog

## [2.4.4] - 2026-10-13

Small fixes. No configuration changes are needed. Use this release instead of 2.4.3.

- Fixed a timing bug when the selected sensors change while the hub is connected to Home Assistant:
  Home Assistant's first reply could arrive before the hub had noted which subscription it belonged
  to, and was thrown away. The hub then reported `ha_streaming: false` and missed live changes
  until the next reconnect. The subscription is now noted before the request is sent.
- Updated pydantic to 2.14.0 and the ruff check to 0.17 or newer (both are tooling and library
  updates with no change in behaviour).

## [2.4.3] - 2026-10-13

Small fix. No configuration changes are needed.

- The system telemetry now also sends `ha_streaming`: true only while the Home Assistant websocket
  is logged in and the hub's subscription to sensor changes is accepted and working. Until now a
  fresh `ha_last_message_at` only showed the connection was alive, because ping replies keep
  arriving even if the subscription was refused. It is null when Home Assistant is not set up,
  false when it is set up but not streaming, and null while no sensors are selected
  (there is nothing to watch).
- Uses central-core-mqtt-shared v1.4.0.

## [2.4.2] - 2026-10-13

Small fixes. No configuration changes are needed.

- The hub now tells the vault when it last heard anything at all from Home Assistant
  (`ha_last_message_at`, a UTC time), ping replies included. `ha_last_event_at` only moves when a
  watched sensor changes, so a quiet house looked the same as a dead feed. Now the vault can tell
  them apart. It is null when Home Assistant is not set up or nothing has been heard yet, and it
  keeps its last value while the connection is down.
- The system telemetry now carries the `cpu` and `ram` fields of the shared MQTT protocol (v1.3.0),
  as percentages (the older `cpu_percent` and memory fields are still sent). `ram` counts memory
  the system can give back from its caches as free. A reading that cannot be taken is left out
  instead of made up.
- Uses central-core-mqtt-shared v1.3.0.

## [2.4.1] - 2026-10-12

Small fixes. No configuration changes are needed.

- Status telemetry now sends `ha_connected` and `ha_last_event_at` as null when Home Assistant is
  not set up on this hub, so the vault does not treat a hub that never had Home Assistant as
  disconnected. `false` still means set up but not connected.
- `config.yaml` now uses the correct `host_network: true` option (it matches `config.json`).

## [2.4.0] - 2026-10-11

Security and reliability hardening. No configuration changes are needed.

- Store and confirm: retained acknowledgements are ignored, and an acknowledgement must name this
  hub's outbox and can only confirm readings the hub has actually sent. The outbox starts a new id
  each time the add-on starts (readings still waiting are kept and sent again under it; nothing is
  deleted), so restoring a Home Assistant backup can no longer make the vault drop new readings as
  duplicates. A restored backup is also detected while running. A reading paho queued while the
  connection was down now counts as sent.
- Commands from the vault must carry a command id and a timestamp (the vault already sends both),
  so old or repeated commands are refused. Reply topics are always validated.
- A client id that isn't a safe MQTT topic level now stops the add-on with a clear log message,
  instead of subscribing to other hubs' commands.
- Home Assistant connection: the address is checked on every connection rather than once at start,
  so a changed address (DHCP) is followed, and a name that doesn't resolve yet at boot (after a power
  cut) is retried instead of switching Home Assistant off until the next restart. IPv4 is preferred.
  A bad port in `ha_api_url` now only switches the Home Assistant link off; MQTT keeps running.
- Status telemetry now includes `ha_connected` and `ha_last_event_at`, so the vault can tell when a
  hub is online but no longer hearing from Home Assistant.
- Tokens, passwords and keys are blanked from debug-log previews.
- Smaller image: tools not used at run time are no longer installed.

Upgrade notes: no vault change is needed first; the vault already sends command ids and timestamps
and names the outbox in its acknowledgements. After updating, the vault logs one "new outbox" line
per hub restart; that is expected.

## [2.3.0] - 2026-10-02

Store and confirm: the hub keeps every reading until the vault confirms it stored it
(`central-core-mqtt-shared` protocol 1.1).

- Every state change and status message is first written to an on-disk outbox
  (`/data/outbox.db`, SQLite, kept through restarts and power cuts) with a sequence number, the time
  it happened (Home Assistant's `last_changed`, in UTC) and, separately, the time the hub queued it.
  It is then sent at QoS 1 (it was QoS 0).
- The vault answers on `hubs/<id>/v1/ack` (`{"upto": N, "stored": K}`) once it has stored
  everything up to N; the hub then deletes those readings.
- After a reconnect, everything the vault has not confirmed is resent, oldest first, in batches of
  20 a second on `hubs/<id>/v1/telemetry/batch`, each reading with its own time, so readings sent
  hours late are stored at the minute they happened. A reading not confirmed within 5 minutes is
  sent again; the vault ignores duplicates.
- Nothing is resent until the vault has confirmed this outbox once, so a vault older than protocol
  1.1 sees no extra traffic; readings are kept (within the caps) until it is updated.
- The outbox is capped at 7 days and 50 MB; beyond that the oldest readings are dropped and the hub
  logs how many (and counts them).
- Each batch carries the hub's clock time so the vault can flag a hub whose clock is wrong.
- Status telemetry includes `outbox` (backlog size, bytes, oldest waiting reading, last confirmed
  sequence number, readings dropped), shown on the vault's hub page.
- Not changed: the hourly sensor list, the sensor list sent on connect and poll replies are still
  sent as before (QoS 0, not kept): they describe what exists, not what happened, and the next one
  replaces them.

Upgrade notes: update the vault (with its database migration) before hubs, so acknowledgements
flow from the first message. The MQTT broker must let each hub subscribe to `hubs/<id>/v1/ack`.

## [2.2.2] - 2026-10-02

- The hub now uses the same MQTT protocol package as the vault: `central-core-mqtt-shared` v1.0.2
  (it shipped v1.0.0 before). The only change is that incoming sensor messages keep `attributes`
  and `device_class`; nothing on the wire changes. Both requirement files pin the commit of the `v1.0.2` tag,
  and a test fails if they ever differ.

## [2.2.1] - 2026-10-01

Upgrade notes (behaviour a hub owner may notice):
- Phones and location are never sent. Sensors on Home Assistant Companion app (`mobile_app`) devices
  (battery, Wi-Fi name, activity, ...), device trackers, people, zones, geocoded location sensors and
  anything with coordinates are left out of sensor reports, `sensors/set` and the inventory. A vault
  selection that names one of them stops receiving it; `sensors/set` lists it under `rejected`.
- If the hub cannot read Home Assistant's device registry (websocket down or token not admin), it
  cannot tell which sensors are on phones, so it sends no sensors until it can, and logs why.
  `sensors/set` then fails with `ha_registry_unavailable` and keeps the previous selection.
- Privacy registry (SENSOR_REGISTRY) fails closed. Migration: `registry_mode: allow` with no
  `provide: true` entries used to send everything; it now sends nothing (logged once). To keep sending
  everything, set `registry_mode: all` (everything except `provide: false` entries). An unreadable
  registry or an unknown mode also sends nothing. No registry at all (the shipped default; the file
  is not in the image unless `registry/set` wrote one) still sends everything, as before.
- A plain `http://` Home Assistant URL whose host does not resolve at start-up is now refused (HA
  integration off, with a log line) instead of accepted. `http://localhost:8123`,
  `http://homeassistant:8123` and `https://` URLs are unaffected.
- The start-up warning when `mqtt_tls` is off now names the broker and points to the TLS plan. The
  default stays `mqtt_tls: false` / 1883 in this release.

- security: the privacy registry is one rule (privacy.py) used by every path; errors deny.
- security: inventory drops Zigbee nodes, and links to them, for devices the registry hides.
- security: inventory keeps at most 3 runs; a second part-1 while one is running is refused (`busy`)
  unless the first is over 60 s old; collecting takes at most 45 s (`timeout`).
- security: at most 100 inbound commands wait for the worker; more, and any message over 64 KB, are
  dropped before queueing and logged (at most once per 10 s).
- docs: docs/security/mqtt-tls-and-command-signing.md, the plan for TLS by default, per-hub
  credentials and signed commands.

## [2.2.0] - 2026-10-01

Upgrade notes (behaviour a hub owner may notice):
- New read-only command `cmd/inventory/get` for the vault's floor plans. On request the hub reports
  Home Assistant's floors, areas and devices (names, makers, models, areas, Zigbee addresses and
  entity ids) and ZHA's Zigbee link readings, in pages of at most 96 KB. It needs the admin token the
  hub already uses. It never sends locations, entity states or attributes; entities are limited to
  sensor, binary_sensor, switch, climate and media_player, and the privacy registry applies.
- Zigbee2MQTT devices are listed from Home Assistant's device registry. Their links are not read
  yet (that needs a network-map scan).

- feat: `inventory/get` (inventory.py), answered from a 10-minute page store; failures carry a
  reason (`ha_unreachable`, `token_not_admin`, `too_large`, `run_expired`).

## [2.1.0] - 2026-09-25

Upgrade notes (behaviour a hub owner may notice):
- If `mqtt_tls` is on and TLS cannot be set up, the hub now refuses to connect instead of silently
  falling back to plaintext. Check the certificate options before updating a hub that uses TLS.
- The Home Assistant token is never sent over plain http/ws to another machine; https, localhost,
  homeassistant, supervisor and this host's own addresses are allowed. Otherwise HA integration is
  turned off with a log line.
- `sensors/set` accepts only a list of entity ids (what the vault sends). `registry/set` is refused
  unless a registry token is configured.
- The default `client_id` is now empty: a new install uses the certificate CN, then the hostname,
  then a stored random id. Existing installs keep their current value.

- security: `sensors/set` could be made to call any Home Assistant service with the add-on's token
  (unchecked entity ids in an HA URL). Entity ids are now validated everywhere they reach HA.
- security: only `sensor.*` and `binary_sensor.*` can be selected; tokens, entity pictures,
  location and anything that looks like a secret are stripped from published attributes.
- security: retained, repeated, oversized, foreign-topic and stale (over 10 minutes) commands are
  ignored or refused.
- security: logs show topic, size and result only; payloads only with the new `debug_logging` option,
  redacted and truncated. `mqtt_password` and `ha_api_token` are password fields.
- security: dependencies pinned exactly; the shared package pinned to a commit; base image 3.24.
- perf: the websocket subscribes only to the selected sensors, and the 30 s full state poll runs
  only while the websocket is down.
- perf: commands and the on-connect publish run off the MQTT network thread; one reconnect loop with
  backoff (1-120 s) and a Last Will, so the vault learns quickly when a hub drops off.
- perf: the outbox is append-only and capped at 1000 items / 1 MiB; faster start-up (importing the
  MQTT client takes about 120 ms instead of 315 ms).
- fix: `sensors/poll` no longer overwrites the selected-sensor list.
- fix: readings carry Home Assistant's real change time, and every timestamp is sent in UTC (the
  add-on kept the offset it started with, so a hub started in summer sent +01:00 all winter).
- fix: system telemetry no longer fails every cycle and now includes the Home Assistant version.

## [2.0.47] - 2026-09-24

- fix: updates and update checks run on their own worker thread. They ran on the MQTT client's
  network thread, which for the minutes a store reload can take stopped the hub sending
  keepalives and sensor changes, and held back the update's own replies.
- fix: a second update or check ordered while one is running is refused with
  "update_already_running" instead of queueing behind it.

## [2.0.46] - 2026-09-24

- fix: the "update started" reply is delivered before Home Assistant stops the add-on to install
  the update (it could be lost, leaving the vault unsure the update had begun).
- fix: after reloading the store, waits up to 30 seconds for the ordered version to appear on Home
  Assistant's update entity, which refreshes on its own schedule, before reporting "not visible yet".

## [2.0.45] - 2026-09-24

- fix: checking for updates reloads the add-on store reliably. Home Assistant gives these calls
  10 seconds by default and a store reload takes longer, so the new version was often not seen.

## [2.0.44] - 2026-09-24

- fix: an update ordered while Home Assistant restarts reports "update entity not found" instead of
  failing with an internal error.

## [2.0.43] - 2026-09-24

- fix: updates ordered from the vault work again, through Home Assistant's update entity.
- feat: `config/check_update` command reports installed and available versions.
- change: Home Assistant's own auto-update is switched off for this add-on at start-up, so updates
  happen only when ordered from the vault.

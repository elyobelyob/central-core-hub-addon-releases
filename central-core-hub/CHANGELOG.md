# Changelog

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

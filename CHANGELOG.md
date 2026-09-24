# Changelog

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

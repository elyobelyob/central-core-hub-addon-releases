# Changelog

## [2.0.44] - 2026-09-24

- fix: an update ordered while Home Assistant restarts reports "update entity not found" instead of
  failing with an internal error.

## [2.0.43] - 2026-09-24

- fix: updates ordered from the vault work again. They now go through Home Assistant's update
  entity (`update.install`) after reloading the add-on store; the services used before
  (`hassio.addon_update`, `check_addon_updates`) no longer exist in Home Assistant.
- feat: `config/check_update` command reports installed and available versions.
- change: Home Assistant's own auto-update is switched off for this add-on at start-up, so updates
  happen only when ordered from the vault.
- deps: pydantic 2.13.5, websocket-client 1.9.2; declare PyYAML; pin central-core-mqtt-shared v1.0.2.
- ci: lint against the rule set the code was written for (newer Ruff defaults had turned CI red).

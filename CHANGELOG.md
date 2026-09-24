# Changelog

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

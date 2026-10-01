# AGENTS.md: Central Core workspace

Guidance for coding agents. The same file lives at the root of every Central Core repo and in the `cc-all` workspace folder that holds them all; when you change it, change every copy.

## What Central Core is

Home monitoring for people living with dementia: a few door and motion sensors, no cameras or microphones, and a plain-English morning update for the family. It is pre-launch. Today it watches the owner's parents' home (Rookery) and the owner's flat (Irongate), but **build everything as a future multi-customer health-data product**: scope every query to a home, rate-limit anything that sends messages, and never shortcut security because "it's only one family".

## Repos and how they fit

| Repo | What it is | Talks to |
|---|---|---|
| `central-core-vault` | Flask + Postgres 15 + Alembic. Staff admin UI, fleet manager, client API, floor plans, Herbert Protocol, reports. **Owns all design and data.** | Hubs over MQTT; client portal over HTTP |
| `central-core-client` | Flask family portal. No database: everything goes through the vault client API with a service token. | Vault `/api/client/v1` |
| `central-core-hub-addon-releases` | Home Assistant add-on that runs in each home (`central-core-hub/`). Only supplies data; never designs or stores plans. | Vault over MQTT |
| `central-core-mqtt-shared` | Shared MQTT topic and payload definitions. | Used by vault and add-on |
| `central-core.com` | Public marketing site, Flask + SQLite. Pre-launch; says so. | Nothing |

Homes: `rookery-001` (ZHA, bungalow) and `elyob-main-001` (Zigbee2MQTT, flat). Both single floor. Floor plans and mapping for every building belong to the vault, not to a hub.

## Commands

| Repo | Test | Lint / types | Deploy |
|---|---|---|---|
| vault | `make test` (starts test Postgres on port 5433 with `make pg-up`; Docker must run). Single files: `TEST_POSTGRES_URL=postgresql+psycopg://vault:vault@127.0.0.1:5433/vault_test .venv/bin/python -m pytest -q <files>` | `make lint` (ruff), `npx --no-install eslint`, `npx --no-install prettier --check` on JS you touch | `./deploy.sh` → 192.168.0.28 (pushes `main`, compose up, `alembic upgrade head`) |
| client | `pytest -q` | — | `CLIENT_HOST=192.168.0.27 ./deploy.sh` |
| add-on | `pytest` | `ruff check .`, `pyright` | Tag `vX.Y.Z` on `main`; the release workflow builds the image. Then order hubs to update from the vault. |
| mqtt-shared | `make test` | — | — |
| website | `cd app && ../venv/bin/python -m pytest -q test_app.py` | — | `./deploy.sh` → 192.168.0.24 |

The full vault suite takes ~13 minutes in CI. The test Postgres is shared: if two agents run vault tests at once, give one its own database (`create database vault_test_<name>`), or tests fail at random.

## Rules that have bitten us

- **Deploy order:** vault first, then client. Client pages call vault endpoints that must already exist.
- **Never deploy from a dirty tree.** The website's `deploy.sh` runs `git add -A` on `main`.
- **Add-on versions:** never run `version_manager.py bump`; it wipes changelog history. Write the changelog entry by hand and set versions with `version_manager.py set`.
- **New hub releases** must be added to the vault's firmware list before hubs can be pushed to them.
- **Tests must not leak patches.** Use `monkeypatch.setattr`, never `module.attr = fake`. Leaked fakes of `request` and `current_user` once broke unrelated tests only in the full run.
- **Stacking layers (vault UI):** use the `--z-*` tokens in `app/static/styles/vault-ui.css`, never raw `z-index` numbers. A test enforces this. Third-party widgets like Leaflet are isolated.
- **Vault vs portal look:** vault is purple (staff), portal is teal (families). Keep them distinct.
- **Roles:** vault roles are viewer, editor, admin, superadmin. Only superadmins delete hubs or grant superadmin. Portal roles are viewer and Lead.
- **Secrets:** never commit `.env*`, keys or certs, and never print secret values in logs or chat. Server secrets live in `.env.prod` on each host. GitGuardian flags made-up test passwords; check before dismissing.
- **Personal data:** the family floor-plan view and the Herbert police sheet never include address, coordinates or ids. Logs mask email addresses and phone numbers. Share tokens are stored hashed and redacted from access logs.
- **Hubs:** never order hub updates or delete hubs without the owner's go-ahead.

## Working style

- Small commits on a `claude/<topic>` branch. Open a PR, wait for CI, merge, then deploy.
- Run the tests for what you touched, plus `tests/test_security_hardening.py` in the vault.
- After deploying, check the live site and the logs before saying it's done.
- Write user-facing text in plain English for families who aren't technical.

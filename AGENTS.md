# AGENTS.md: central-core-hub-addon-releases

## Central Core in one paragraph

Home monitoring for people living with dementia: a few door and motion sensors, no cameras or microphones, and a plain-English morning update for the family. Pre-launch: today it watches the owner's parents' home (`rookery-001`) and the owner's flat (`elyob-main-001`), but **build it as a future multi-customer health-data product**. Scope every query to a home, rate-limit anything that sends messages, and never cut a security corner because "it's only one family".

The five repos sit side by side in a `cc-all` folder: `central-core-vault` (owns all data and design), `central-core-client` (family portal, talks only to the vault API), `central-core-hub-addon-releases` (Home Assistant add-on in each home, talks to the vault over MQTT), `central-core-mqtt-shared` (the MQTT protocol), `central-core.com` (public website). `cc-all/AGENTS.md` has the whole-system view.

## Everywhere

- Small commits on a `claude/<topic>` branch, a PR, green CI, merge, then deploy. Check the live result and logs before calling it done.
- Never commit `.env*`, keys or certs; never print secret values. GitGuardian flags made-up test passwords, so check before dismissing.
- Tests use `monkeypatch.setattr`, never `module.attr = fake` (leaked fakes broke unrelated tests in the full run).
- Write anything families read in plain English.
- **Never give medical advice, anywhere**: portal, morning updates, care reports, AI prompts, emails, the website and marketing. Describe only what the sensors showed and how it compares with that home's usual pattern. Never name, suggest or guess at an illness, infection or condition; never say something is a sign or symptom; never mention doctors, medication or treatment. This is an owner rule, and it also keeps Central Core outside medical-device regulation (MHRA). The most we ever suggest is that the family checks in.

## This repo

The Home Assistant add-on that runs in each home (`central-core-hub/`). It **only supplies data**: sensor states, telemetry, inventory. It never designs floor plans or stores customer data; the vault does that.

## Commands

- Tests: `pytest`. Lint and types: `ruff check .` and `pyright` (CI runs all three). A pre-push hook runs the whole CI locally, so pushes take a few minutes.
- Release: write the `CHANGELOG.md` entry by hand, set the version by editing `central-core-hub/config.json`, `central-core-hub/config.yaml` and `repository.json`, then run `python3 version_manager.py validate`. Never run `version_manager.py bump` or `set`: both wipe the changelog history, merge to `main`, then tag `vX.Y.Z`. The release workflow builds the image.
- After a release, the vault's firmware list needs the new version before hubs can be pushed to it. Never push hub updates without the owner's go-ahead.

## Rules

- Commands from MQTT are untrusted: check `command_id`, size (64 KB) and type; the queue is bounded.
- Privacy fails closed (`privacy.py`). Phones, people, zones, trackers and anything with coordinates never leave the hub, on every path (poll, set, publishes, inventory).
- Never change defaults that would disconnect existing hubs (for example MQTT TLS) without a migration plan; see `docs/security/mqtt-tls-and-command-signing.md`.
- The MQTT protocol comes from `central-core-mqtt-shared`. Both `requirements.txt` and `central-core-hub/requirements.txt` pin the exact commit of the same release tag the vault pins (currently `v1.1.0`; TODO: the commit is a placeholder until the tag exists); `tests/unit/test_mqtt_shared_pin.py` enforces the match.

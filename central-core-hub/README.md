# Central Core Hub Add-on

This repository folder contains the Home Assistant Supervisor add-on for Central Core Hub.

Installation (from Supervisor add-on store):

Notes:
docker build -t ghcr.io/elyobelyob/central-core-hub:1.0.0 .
# Central Core Hub Home Assistant Add-on

This folder contains the Home Assistant Supervisor add-on for Central Core Hub, designed for reliable use on Home Assistant OS (HAOS) and other Supervisor-based installations.

## Features
- Prebuilt multi-arch Docker image (GHCR)
- Supervisor build support (`Dockerfile` + `build.yaml`)
- Host networking, minimal permissions
- CI/CD for automated builds and releases

## Installation (HAOS/Supervisor)
1. **Add this repository to your Add-on Store:**
	 - Go to Home Assistant UI → Supervisor → Add-on Store
	 - Click the three dots (top right) → Repositories
	 - Add:
		 ```
		 https://github.com/elyobelyob/central-core-hub-addon-releases
		 ```
	 - Click Add, then Refresh
2. **Install the add-on:**
	 - Find "Central Core Hub" in the Add-on Store
	 - Click Install, then Start
	 - Check Logs for successful startup

## Build & CI
- Prebuilt images are published to: `ghcr.io/elyobelyob/central-core-hub:<tag>`
- To trigger a new build, push a new git tag (e.g. `1.0.1`). GitHub Actions will build and push multi-arch images.
- Supervisor can also build locally using the included `Dockerfile` and `build.yaml` if no image is available.

## Configuration
- Minimal config: host networking, no extra privileges by default
- To customize, edit `config.yaml`/`config.json` and rebuild/tag as needed

## Troubleshooting
- If the add-on does not appear, check:
	- The repository URL is correct and public
	- The image exists on GHCR (or let Supervisor build it)
	- Supervisor and add-on logs for errors
- For private images, set up a GHCR PAT as described in the main project README

## Contributing
- PRs welcome! Please update the changelog and bump the version/tag for releases.

---

For more details, see the root `README.md` and the Home Assistant [add-on developer docs](https://developers.home-assistant.io/docs/add-ons/).
```

2. Add this repository URL to Home Assistant Supervisor Add-on store:

```text
https://github.com/elyobelyob/central-core-hub-addon-releases
```

3. Refresh the Add-on store. The add-on `Central Core Hub` should appear. Install it — Supervisor will validate `config.yaml` and `config.json`.

4. If the add-on fails validation, check Supervisor logs and ensure the image tag exists and is publicly accessible (or authenticate GHCR).

CI / Auto-build (GitHub Actions):

- This repository includes a workflow: `.github/workflows/release.yml`.
- Push a git tag (for example `1.0.0`) to trigger the workflow which will build multi-arch images and push them to `ghcr.io/elyobelyob/central-core-hub:<tag>` and `:latest`.

HAOS reliability notes

- `init: true` is enabled so the container runs with proper init handling.
- `stage: stable` and `timeout: 30` are set in the add-on config to help Supervisor manage lifecycle.
- `ports` and `watchdog` are provided (web UI assumed on port `8080`) — Supervisor will use the `watchdog` URL to validate add-on health.
- The Docker image includes `io.hass.*` labels (build-time) to improve Supervisor compatibility.

If you want HAOS to build the add-on locally instead of pulling from GHCR, Supervisor will use `Dockerfile` and `build.yaml` from the add-on folder. Building on the Pi can be slow; pushing prebuilt images to GHCR is faster for users.

Example (create annotated tag and push):

```bash
git tag 1.0.0
git push origin 1.0.0
```

Notes on authentication:
- The workflow uses `${{ secrets.GITHUB_TOKEN }}` to authenticate to GitHub Container Registry (GHCR). Ensure Actions has `packages: write` permission (it is set in the workflow). In some orgs, you may need a Personal Access Token with `write:packages` stored in `secrets.GHCR_PAT` and the workflow adjusted to use it.

Using a Personal Access Token (recommended in some orgs):

1. Create a PAT with these scopes: `repo` (if private repo) and `write:packages` (to push to GHCR). Optionally `read:packages`.
2. In your repository Settings → Secrets → Actions, add a new secret named `GHCR_PAT` containing the PAT value.
3. The workflow will prefer `GHCR_PAT` when present; otherwise it falls back to the default `GITHUB_TOKEN`.

If you want me to add sample `icon.png`/`logo.png` raster files or to create a GitHub Actions job that also builds release notes, tell me and I'll add them.

Supervisor builds:
- A `Dockerfile` and `build.yaml` are included, so Supervisor or the Home Assistant build system can build the add-on locally if you prefer not to use the prebuilt GHCR image.

If you want me to also add a `logo.png`, `run.sh`, or a Dockerfile/build files, tell me which approach you prefer (prebuilt image vs. build in Supervisor).

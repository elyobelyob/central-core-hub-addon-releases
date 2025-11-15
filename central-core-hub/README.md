# Central Core Hub Add-on

This repository folder contains the Home Assistant Supervisor add-on for Central Core Hub.

Installation (from Supervisor add-on store):
- Add this repository URL to your Home Assistant Add-on store: `https://github.com/elyobelyob/central-core-hub-addon-releases`
- Install the `Central Core Hub` add-on.

Notes:
- This add-on pulls the image `ghcr.io/elyobelyob/central-core-hub:latest`.
- The add-on `version` field is set to `latest` to match the image tag.
- If you publish releases/tags for the image, update the `version` field to match the image tag.

Current configuration in this repository:
- `version`: `1.0.0`
- `image`: `ghcr.io/elyobelyob/central-core-hub:1.0.0`

Publishing & testing steps (recommended):
1. Build and push your Docker image with the `1.0.0` tag:

```bash
# build locally (example)
docker build -t ghcr.io/elyobelyob/central-core-hub:1.0.0 .
docker push ghcr.io/elyobelyob/central-core-hub:1.0.0
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

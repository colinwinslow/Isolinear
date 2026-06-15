---
status: draft
date: 2026-06-14
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0011
---

# Home Assistant Integration: HACS Install Packaging

## Status

Draft. Defines the first HACS-compatible packaging surface for installing and
updating Isolinear as a custom Home Assistant integration.

## Related Docs

- [bdd/integration/home-assistant-hacs-install-packaging-bdd.md](../../bdd/integration/home-assistant-hacs-install-packaging-bdd.md) - observable behavior
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md) - integration package scaffold
- [docs/specs/home-assistant-dashboard-resource-registration-spec.md](home-assistant-dashboard-resource-registration-spec.md) - card resource serving
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

Manual install currently requires copying `custom_components/isolinear`,
`frontend/dist/isolinear-card.js`, and `docs/schemas` into a Home Assistant
config directory. That does not match the normal HACS custom-repository update
loop.

HACS integration repositories install the integration directory under
`custom_components/<domain>/`. Therefore all runtime files required by
Isolinear must be available inside `custom_components/isolinear/`.

## Behavior Contract

The repository must be installable as a HACS custom repository of type
`integration`.

The package must:

- Provide a root `hacs.json` with the HACS display name.
- Keep exactly one integration under `custom_components/`: `isolinear`.
- Include a Home Assistant `manifest.json` with HACS-required metadata,
  including `issue_tracker`.
- Include local Home Assistant brand icons under
  `custom_components/isolinear/brand/`, with at least `icon.png`.
- Bundle the JSON Schemas used by the runtime validators under
  `custom_components/isolinear/schemas/`.
- Bundle the dashboard card module under
  `custom_components/isolinear/frontend/dist/isolinear-card.js`.
- Serve the dashboard card from the bundled integration asset path while
  preserving the static asset path `/api/isolinear/static/isolinear-card.js`
  and registering Lovelace metadata with a package-versioned query string for
  cache busting.
- Load runtime schemas from the installed integration package, not from repo
  root `docs/schemas`.
- Keep the repo-root `docs/schemas` as the authoring source and prove packaged
  schemas match it byte-for-byte.

Allowed side effects are limited to repository packaging metadata, packaged
runtime assets, path resolution, README/install documentation, and tests/eval
evidence.

## Anchor Artifact

The anchor artifact is a HACS-shaped repository tree:

- `hacs.json`
- `custom_components/isolinear/manifest.json`
- `custom_components/isolinear/brand/icon.png`
- `custom_components/isolinear/schemas/*.schema.json`
- `custom_components/isolinear/frontend/dist/isolinear-card.js`
- package-local path resolution in `custom_components/isolinear/_paths.py`

## Implementation Order

1. Add this spec and paired BDD/evidence scaffold.
2. Add HACS metadata and package-local runtime paths.
3. Add package-local brand icons.
4. Copy runtime schemas and the dashboard card bundle into the integration
   package.
5. Update the frontend build helper to refresh the packaged card bundle.
6. Add focused pytest and a thin eval for the HACS packaging contract.
7. Verify the files on disk.

## Proof Requirements

1. Focused pytest proves HACS metadata, one-integration repository shape,
   manifest metadata, package-local brand icons, package-local schema paths,
   bundled schema parity, and bundled card asset path.
2. Eval evidence maps the same checks to the BDD scenarios.
3. Existing dashboard resource tests remain green with the bundled card path.
4. Existing first-real-slice and worker-rendered artifact tests remain green
   with packaged schema paths.
5. Real artifacts are verified on disk.

## Non-Goals

- Publishing a GitHub release.
- Submitting Isolinear to the default HACS store.
- Building a separate worker add-on package.
- Creating a Home Assistant Repairs/UI flow for worker token provisioning.
- Changing card-facing WebSocket commands.
- Changing model-provider, worker, renderer, entity allowlist, history, or
  artifact-serving behavior.

## References

- [HACS general publish requirements](https://www.hacs.xyz/docs/publish/start/)
- [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/)
- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)

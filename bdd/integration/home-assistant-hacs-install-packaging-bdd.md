# Home Assistant Integration: HACS Install Packaging - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-hacs-install-packaging.md](../../docs/specs/home-assistant-hacs-install-packaging.md).

Evidence file:

- `bdd/integration/home-assistant-hacs-install-packaging-evidence.md`

## Why This BDD Exists

This BDD pins down the install/update loop expected by Home Assistant users who
manage custom integrations through HACS. It proves Isolinear can be downloaded
as a HACS custom integration without manual copying of schemas or dashboard
assets after each small update.

## Scenarios

### Scenario A - happy path: repository is HACS-shaped

**Given** the repository root is used as a HACS custom repository
**When** HACS inspects the repository metadata
**Then** root `hacs.json` should identify Isolinear
**And** `custom_components/` should contain exactly one integration directory,
`isolinear`

### Scenario B - happy path: integration manifest is HACS-ready

**Given** the Isolinear integration manifest exists
**When** HACS validates integration metadata
**Then** the manifest should include `domain`, `name`, `version`,
`documentation`, `issue_tracker`, and `codeowners`

### Scenario C - happy path: runtime schemas are bundled

**Given** HACS installs only `custom_components/isolinear`
**When** Isolinear validation code resolves JSON Schemas
**Then** schema paths should point inside `custom_components/isolinear/schemas`
**And** every packaged schema should match the repo-root authoring schema

### Scenario D - happy path: dashboard card is bundled

**Given** HACS installs only `custom_components/isolinear`
**When** Isolinear registers the dashboard card static path
**Then** the bundled card file should exist inside
`custom_components/isolinear/frontend/dist`
**And** the public card URL should remain
`/api/isolinear/static/isolinear-card.js`

### Scenario E - maintenance path: frontend builds refresh the packaged card

**Given** a developer rebuilds the frontend bundle
**When** the repo-local frontend build helper succeeds
**Then** the built card bundle should be copied into the integration package
for the next HACS download

## Evidence

The implementing slice produces focused pytest output and raw `CASE` output
from `evals/home_assistant_hacs_install_packaging.py`.

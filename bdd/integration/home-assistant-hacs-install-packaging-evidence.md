# Home Assistant HACS Install Packaging Evidence

Run timestamp: 2026-06-14T15:39:02-07:00

BDD file:
`bdd/integration/home-assistant-hacs-install-packaging-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: repository is HACS-shaped -> `CASE repository_is_hacs_shaped`
- Scenario B: integration manifest is HACS-ready -> `CASE manifest_is_hacs_ready`
- Scenario C: runtime schemas are bundled -> `CASE runtime_schemas_are_bundled`
- Scenario D: dashboard card is bundled -> `CASE dashboard_card_is_bundled`
- Scenario E: frontend builds refresh the packaged card -> `CASE frontend_build_refreshes_packaged_card`

## Verification

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_hacs_install_packaging.py tests/test_dashboard_resource_registration_anchor.py tests/test_first_real_vertical_slice.py tests/test_worker_rendered_artifact_serving.py
```

Raw output:

```text
collected 25 items

tests\test_hacs_install_packaging.py .....                               [ 20%]
tests\test_dashboard_resource_registration_anchor.py .......             [ 48%]
tests\test_first_real_vertical_slice.py .......                          [ 76%]
tests\test_worker_rendered_artifact_serving.py ......                    [100%]

============================= 25 passed in 9.30s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_hacs_install_packaging.py
```

Raw output:

```text
CASE repository_is_hacs_shaped
{
  "case_id": "repository_is_hacs_shaped",
  "given": {
    "repository_root": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear"
  },
  "then": {
    "hacs_name": "Isolinear",
    "integration_dirs": [
      "isolinear"
    ],
    "package_dir": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\custom_components\\isolinear",
    "passed": true
  },
  "when": {
    "operation": "inspect_hacs_custom_repository_shape"
  }
}
PASS repository_is_hacs_shaped
CASE manifest_is_hacs_ready
{
  "case_id": "manifest_is_hacs_ready",
  "given": {
    "manifest": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\custom_components\\isolinear\\manifest.json"
  },
  "then": {
    "domain": "isolinear",
    "issue_tracker": "https://github.com/kagwerks/isolinear/issues",
    "missing": [],
    "passed": true
  },
  "when": {
    "operation": "inspect_manifest_metadata"
  }
}
PASS manifest_is_hacs_ready
CASE runtime_schemas_are_bundled
{
  "case_id": "runtime_schemas_are_bundled",
  "given": {
    "packaged_schemas": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\custom_components\\isolinear\\schemas",
    "root_schemas": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\docs\\schemas"
  },
  "then": {
    "mismatched": [],
    "non_package_paths": [],
    "packaged_schema_count": 30,
    "passed": true,
    "root_schema_count": 30
  },
  "when": {
    "operation": "compare_schema_payloads_and_runtime_paths"
  }
}
PASS runtime_schemas_are_bundled
CASE dashboard_card_is_bundled
{
  "case_id": "dashboard_card_is_bundled",
  "given": {
    "root_bundle": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js"
  },
  "then": {
    "bundle_exists": true,
    "bundle_matches_root": true,
    "packaged_bundle": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\custom_components\\isolinear\\frontend\\dist\\isolinear-card.js",
    "passed": true,
    "resource": {
      "type": "module",
      "url": "/api/isolinear/static/isolinear-card.js"
    }
  },
  "when": {
    "operation": "resolve_dashboard_resource_bundle"
  }
}
PASS dashboard_card_is_bundled
CASE frontend_build_refreshes_packaged_card
{
  "case_id": "frontend_build_refreshes_packaged_card",
  "given": {
    "script": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\scripts\\frontend.ps1"
  },
  "then": {
    "checks": {
      "bundle_name": true,
      "copy_item": true,
      "packaged_dist_path": true
    },
    "passed": true
  },
  "when": {
    "operation": "inspect_frontend_build_helper"
  }
}
PASS frontend_build_refreshes_packaged_card
PASS home_assistant_hacs_install_packaging
```

Evidence details:

- `repository_is_hacs_shaped`: `hacs.json` reports `Isolinear`, and
  `custom_components/` contains exactly `isolinear`.
- `manifest_is_hacs_ready`: the manifest includes `domain`, `name`,
  `version`, `documentation`, `issue_tracker`, and `codeowners`.
- `runtime_schemas_are_bundled`: 30 packaged schemas match the 30 repo-root
  authoring schemas, with no runtime schema paths outside
  `custom_components/isolinear/schemas`.
- `dashboard_card_is_bundled`: the packaged card exists at
  `custom_components/isolinear/frontend/dist/isolinear-card.js`, matches the
  repo-root build output, and keeps the public resource URL
  `/api/isolinear/static/isolinear-card.js`.
- `frontend_build_refreshes_packaged_card`: `scripts/frontend.ps1 build`
  contains the packaged-card copy step.

## Frontend Build Verification

Raw command:

```powershell
.\scripts\frontend.ps1 build
```

Raw output:

```text
Node: v24.16.0
npm: 11.13.0

> build
> tsc -p tsconfig.json --noEmit && vite build

vite v8.0.16 building client environment for production...
transforming...✓ 21 modules transformed.
rendering chunks...
computing gzip size...
dist/isolinear-card.js  34.96 kB | gzip: 10.64 kB
✓ built in 165ms
```

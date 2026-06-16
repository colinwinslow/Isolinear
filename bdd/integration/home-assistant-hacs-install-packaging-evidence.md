# Home Assistant HACS Install Packaging Evidence

Run timestamp: 2026-06-16T16:40:11+00:00

BDD file:
`bdd/integration/home-assistant-hacs-install-packaging-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: repository is HACS-shaped -> `CASE repository_is_hacs_shaped`
- Scenario B: integration manifest is HACS-ready -> `CASE manifest_is_hacs_ready`
- Scenario C: brand icons are bundled -> `CASE brand_icons_are_packaged`
- Scenario D: runtime schemas are bundled -> `CASE runtime_schemas_are_bundled`
- Scenario E: dashboard card is bundled -> `CASE dashboard_card_is_bundled`
- Scenario F: frontend builds refresh the packaged card -> `CASE frontend_build_refreshes_packaged_card`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_resource_registration_anchor.py tests/test_hacs_install_packaging.py
```

Raw output:

```text
collected 14 items
tests\test_dashboard_resource_registration_anchor.py ........            [ 57%]
tests\test_hacs_install_packaging.py ......                              [100%]
14 passed in 0.41s
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_hacs_install_packaging.py
```

Raw observed output excerpts:

```text
CASE repository_is_hacs_shaped
"hacs_name": "Isolinear"
"integration_dirs": ["isolinear"]
PASS repository_is_hacs_shaped

CASE manifest_is_hacs_ready
"domain": "isolinear"
"issue_tracker": "https://github.com/kagwerks/isolinear/issues"
"missing": []
PASS manifest_is_hacs_ready

CASE brand_icons_are_packaged
"icon": {"bytes": 59627, "exists": true, "path": "...\\custom_components\\isolinear\\brand\\icon.png"}
"high_density_icon": {"bytes": 218010, "exists": true, "path": "...\\custom_components\\isolinear\\brand\\icon@2x.png"}
PASS brand_icons_are_packaged

CASE runtime_schemas_are_bundled
"root_schema_count": 30
"packaged_schema_count": 30
"mismatched": []
"non_package_paths": []
PASS runtime_schemas_are_bundled

CASE dashboard_card_is_bundled
"packaged_bundle": "...\\custom_components\\isolinear\\frontend\\dist\\isolinear-card.js"
"bundle_exists": true
"bundle_matches_root": true
"expected_resource_url": "/api/isolinear/static/isolinear-card.js?v=0.1.7"
"resource": {"type": "module", "url": "/api/isolinear/static/isolinear-card.js?v=0.1.7"}
PASS dashboard_card_is_bundled

CASE frontend_build_refreshes_packaged_card
"checks": {"packaged_dist_path": true, "copy_item": true, "bundle_name": true}
PASS frontend_build_refreshes_packaged_card

PASS home_assistant_hacs_install_packaging
```

## Manifest Version Readback

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_integration_scaffold.py
```

Raw observed output excerpt:

```text
CASE scaffold_package_is_visible_to_home_assistant
"const_version": "0.1.7"
"const_version_matches_manifest": true
"manifest": {"domain": "isolinear", "version": "0.1.7"}
PASS scaffold_package_is_visible_to_home_assistant

PASS home_assistant_integration_scaffold
```

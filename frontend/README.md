# Isolinear Dashboard Card Anchor

This frontend anchor proves ADR-0011 with a real `custom:isolinear-card`
surface before the Home Assistant integration exists.

The TypeScript source in `src/` is the Lit implementation. The
browser-loadable ES module in `dist/isolinear-card.js` is the checked-in anchor
bundle produced by Vite.

Use the repo-local PowerShell wrappers from the repository root:

```powershell
.\scripts\frontend.ps1 install
.\scripts\frontend.ps1 build
.\scripts\frontend.ps1 test
.\scripts\frontend.ps1 serve -Port 8765
```

The local harness at `harness/index.html` imports the bundle, supplies a fake
Home Assistant object, and renders the fixture job snapshots from
`fixtures/job-snapshots.json`. After starting the server, open
`http://127.0.0.1:8765/harness/`.

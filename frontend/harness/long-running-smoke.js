import "../dist/isolinear-card.js";

const PROMPT = "Show sensor.upstairs_temperature for the last 24 hours";
const SMOKE_ENDPOINT = "/__isolinear_smoke_ws";
const evidenceElement = document.querySelector("#smoke-evidence");
const card = document.querySelector("#card");

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitFor(predicate, timeoutMs = 15000) {
  const startedAt = performance.now();
  while (performance.now() - startedAt < timeoutMs) {
    if (predicate()) {
      return;
    }
    await sleep(50);
  }
  throw new Error("Timed out waiting for the Isolinear card smoke condition.");
}

function pngSignatureHex(dataUrl) {
  if (!dataUrl?.startsWith("data:image/png;base64,")) {
    return null;
  }
  const raw = window.atob(dataUrl.slice("data:image/png;base64,".length));
  return Array.from(raw.slice(0, 8), (char) =>
    char.charCodeAt(0).toString(16).padStart(2, "0"),
  ).join(" ");
}

function summarizeResult(result) {
  const snapshot = result.snapshot ?? result;
  const chartImageUrl = snapshot.chart?.image_url ?? "";
  return {
    accepted: result.accepted ?? true,
    code: result.code ?? null,
    snapshot: {
      snapshot_id: snapshot.snapshot_id,
      job_id: snapshot.job_id,
      status: snapshot.status,
      state_label: snapshot.state_label,
      validation: snapshot.validation,
      chart: snapshot.chart ? {
        title: snapshot.chart.title,
        image_url_prefix: chartImageUrl.slice(0, 30),
        image_url_length: chartImageUrl.length,
        png_signature_hex: pngSignatureHex(chartImageUrl),
        series: snapshot.chart.series,
      } : null,
    },
    orchestration: result.orchestration ?? null,
  };
}

function currentCardSummary() {
  const article = card.shadowRoot?.querySelector("article");
  const image = card.shadowRoot?.querySelector("[data-testid='chart-image']");
  return {
    snapshot_id: card.snapshot?.snapshot_id,
    job_id: card.snapshot?.job_id,
    status: card.snapshot?.status,
    layout: article?.getAttribute("data-layout") ?? null,
    state_label: card.shadowRoot?.querySelector("[data-testid='job-state']")?.textContent ?? null,
    chart_image_visible: Boolean(image?.getAttribute("src")),
    png_signature_hex: pngSignatureHex(image?.getAttribute("src")),
    validation: card.snapshot?.validation ?? null,
  };
}

function createBridgeHass() {
  const calls = [];

  return {
    language: "en",
    themes: { darkMode: false },
    connection: {
      async sendMessagePromise(message) {
        const startedAt = performance.now();
        const response = await fetch(SMOKE_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(message),
        });
        const result = await response.json();
        calls.push({
          request: message,
          response: summarizeResult(result),
          elapsed_ms: Math.round(performance.now() - startedAt),
        });
        if (!response.ok || result.accepted === false) {
          throw new Error(result.code ?? `Smoke bridge rejected ${message.type}`);
        }
        return result.snapshot;
      },
    },
    get isolinearCalls() {
      return calls;
    },
  };
}

function writeEvidence(evidence) {
  evidenceElement.textContent = JSON.stringify(evidence, null, 2);
  evidenceElement.dataset.smokeStatus = evidence.passed ? "passed" : "failed";
  document.body.dataset.smokeStatus = evidence.passed ? "passed" : "failed";
  fetch("/__isolinear_smoke_evidence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(evidence),
  }).catch(() => undefined);
}

async function runSmoke() {
  const startedAt = performance.now();
  const hass = createBridgeHass();
  const states = [];

  card.setConfig({
    type: "custom:isolinear-card",
    config_entry_id: "real-slice-entry",
    title: "Isolinear Smoke",
  });
  card.hass = hass;
  await card.updateComplete;
  states.push({ point: "loaded", card: currentCardSummary() });

  const input = card.shadowRoot.querySelector("[data-testid='prompt-input']");
  input.value = PROMPT;
  input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
  await card.updateComplete;

  const form = card.shadowRoot.querySelector("[data-testid='composer']");
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));
  await waitFor(() => card.snapshot?.status === "complete");
  await card.updateComplete;
  states.push({ point: "complete", card: currentCardSummary() });

  const commandTypes = hass.isolinearCalls.map((call) => call.request.type);
  const failures = [];
  if (commandTypes[0] !== "isolinear/v1/job/start") {
    failures.push("first command was not job/start");
  }
  if (!commandTypes.includes("isolinear/v1/job/snapshot")) {
    failures.push("job/snapshot polling command was not observed");
  }
  if (card.snapshot.status !== "complete") {
    failures.push(`final card status was ${card.snapshot.status}`);
  }
  if (currentCardSummary().layout !== "chart-first") {
    failures.push("complete card did not use chart-first layout");
  }
  if (currentCardSummary().png_signature_hex !== "89 50 4e 47 0d 0a 1a 0a") {
    failures.push("chart image did not expose a PNG data URL signature");
  }

  writeEvidence({
    passed: failures.length === 0,
    failures,
    prompt: PROMPT,
    duration_ms: Math.round(performance.now() - startedAt),
    states,
    command_types: commandTypes,
    calls: hass.isolinearCalls,
  });
}

try {
  await runSmoke();
} catch (error) {
  writeEvidence({
    passed: false,
    failures: [error instanceof Error ? error.message : String(error)],
    prompt: PROMPT,
    card: currentCardSummary(),
  });
}

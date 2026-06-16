// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from "vitest";
import { ISOLINEAR_COMMANDS, ISOLINEAR_WS_VERSION } from "./isolinear-api";
import { IsolinearCard } from "./isolinear-card";
import type { HomeAssistantLike, IsolinearJobSnapshot } from "./types";

const SERVED_PNG_URL = "/api/isolinear/artifacts/smoke-artifact-001.png";

const planningSnapshot: IsolinearJobSnapshot = {
  snapshot_id: "smoke-planning",
  job_id: "job-smoke-001",
  status: "planning",
  prompt: "Show sensor.upstairs_temperature for the last 24 hours",
  state_label: "Planning",
  progress: {
    stage: "planning",
    message: "Resolving approved entities and drafting a chart spec.",
  },
  validation: { status: "pending", summary: "Waiting for validation." },
  warnings: [],
};

const completeSnapshot: IsolinearJobSnapshot = {
  snapshot_id: "smoke-complete",
  job_id: "job-smoke-001",
  status: "complete",
  prompt: "Show sensor.upstairs_temperature for the last 24 hours",
  state_label: "Complete",
  chart: {
    title: "Browser Smoke Upstairs Temperature",
    image_url: SERVED_PNG_URL,
    time_range: "Last 24 hours",
    series: [
      {
        series_id: "sensor_upstairs_temperature",
        label: "Upstairs Temperature",
        entity_id: "sensor.upstairs_temperature",
      },
    ],
    overlays: [],
  },
  entities: [
    {
      entity_id: "sensor.upstairs_temperature",
      label: "Upstairs Temperature",
    },
  ],
  aliases: [],
  validation: {
    status: "pass",
    summary: "Chart spec, allowlist, image artifact, and render metadata passed.",
  },
  warnings: [],
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(predicate: () => boolean, timeoutMs = 1000): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (predicate()) {
      return;
    }
    await sleep(5);
  }
  throw new Error("Timed out waiting for mounted Isolinear card smoke condition.");
}

function createDelayedHass() {
  const calls: Array<Record<string, unknown>> = [];
  const hass: HomeAssistantLike = {
    connection: {
      async sendMessagePromise(message: Record<string, unknown>) {
        calls.push(message);
        await sleep(5);
        if (message.type === ISOLINEAR_COMMANDS.startJob) {
          return planningSnapshot;
        }
        if (message.type === ISOLINEAR_COMMANDS.getSnapshot) {
          return completeSnapshot;
        }
        throw new Error(`Unexpected Isolinear smoke command: ${message.type}`);
      },
    },
  };

  return { hass, calls };
}

function createRejectingHass() {
  const calls: Array<Record<string, unknown>> = [];
  const hass: HomeAssistantLike = {
    connection: {
      async sendMessagePromise(message: Record<string, unknown>) {
        calls.push(message);
        throw { code: "unknown_config_entry", message: "The Isolinear config entry was not found." };
      },
    },
  };

  return { hass, calls };
}

function createTimeoutThenCompleteHass() {
  const calls: Array<Record<string, unknown>> = [];
  let snapshotPolls = 0;
  const hass: HomeAssistantLike = {
    connection: {
      async sendMessagePromise(message: Record<string, unknown>) {
        calls.push(message);
        await sleep(5);
        if (message.type === ISOLINEAR_COMMANDS.startJob) {
          return planningSnapshot;
        }
        if (message.type === ISOLINEAR_COMMANDS.getSnapshot) {
          snapshotPolls += 1;
          if (snapshotPolls === 1) {
            throw { code: "timeout", message: "Timed out waiting for the job snapshot." };
          }
          return completeSnapshot;
        }
        throw new Error(`Unexpected Isolinear smoke command: ${message.type}`);
      },
    },
  };

  return { hass, calls };
}

function createRepeatedHomeAssistantTimeoutThenCompleteHass() {
  const calls: Array<Record<string, unknown>> = [];
  let snapshotPolls = 0;
  const hass: HomeAssistantLike = {
    connection: {
      async sendMessagePromise(message: Record<string, unknown>) {
        calls.push(message);
        await sleep(5);
        if (message.type === ISOLINEAR_COMMANDS.startJob) {
          return planningSnapshot;
        }
        if (message.type === ISOLINEAR_COMMANDS.getSnapshot) {
          snapshotPolls += 1;
          if (snapshotPolls <= 8) {
            throw { code: "fail", message: "Timed out waiting for the job snapshot." };
          }
          return completeSnapshot;
        }
        throw new Error(`Unexpected Isolinear smoke command: ${message.type}`);
      },
    },
  };

  return { hass, calls };
}

function createTerminalSnapshotRejectionHass() {
  const calls: Array<Record<string, unknown>> = [];
  const hass: HomeAssistantLike = {
    connection: {
      async sendMessagePromise(message: Record<string, unknown>) {
        calls.push(message);
        await sleep(5);
        if (message.type === ISOLINEAR_COMMANDS.startJob) {
          return planningSnapshot;
        }
        if (message.type === ISOLINEAR_COMMANDS.getSnapshot) {
          throw { code: "unknown_job", message: "The Isolinear job was not found." };
        }
        throw new Error(`Unexpected Isolinear smoke command: ${message.type}`);
      },
    },
  };

  return { hass, calls };
}

describe("Isolinear mounted card long-running smoke", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("uses automatic config-entry resolution in the picker stub config", () => {
    expect(IsolinearCard.getStubConfig().config_entry_id).toBe("auto");
  });

  it("normalizes the legacy fake config entry placeholder to auto", async () => {
    const { hass, calls } = createRejectingHass();
    const card = new IsolinearCard();
    document.body.append(card);
    card.setConfig({
      type: "custom:isolinear-card",
      config_entry_id: "fake-config-entry",
      title: "Isolinear",
    });
    card.hass = hass;
    await card.updateComplete;

    const input = card.shadowRoot!.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")!;
    input.value = "Show sensor.family_room_sensor_temperature";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await card.updateComplete;

    const form = card.shadowRoot!.querySelector<HTMLFormElement>("[data-testid='composer']")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));

    await waitFor(() => card.snapshot.status === "failed");

    expect(calls).toEqual([
      {
        type: ISOLINEAR_COMMANDS.startJob,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: "auto",
        prompt: "Show sensor.family_room_sensor_temperature",
      },
    ]);
  });

  it("shows auto in the editor when Home Assistant passes the legacy fake config entry placeholder", async () => {
    const editor = IsolinearCard.getConfigElement() as HTMLElement & {
      setConfig(config: Record<string, unknown>): void;
      updateComplete: Promise<unknown>;
    };
    document.body.append(editor);
    editor.setConfig({
      type: "custom:isolinear-card",
      config_entry_id: "fake-config-entry",
      title: "Isolinear",
    });
    await editor.updateComplete;

    expect(editor.shadowRoot!.querySelector<HTMLInputElement>("input")!.value).toBe("auto");
  });

  it("polls job/snapshot until a delayed prompt renders a PNG chart", async () => {
    const { hass, calls } = createDelayedHass();
    const card = new IsolinearCard();
    card.snapshotPollIntervalMs = 5;
    document.body.append(card);
    card.setConfig({
      type: "custom:isolinear-card",
      config_entry_id: "real-slice-entry",
      title: "Isolinear Smoke",
    });
    card.hass = hass;
    await card.updateComplete;

    const input = card.shadowRoot!.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")!;
    input.value = "Show sensor.upstairs_temperature for the last 24 hours";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await card.updateComplete;

    const form = card.shadowRoot!.querySelector<HTMLFormElement>("[data-testid='composer']")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));

    await waitFor(() => card.snapshot.status === "planning");
    await card.updateComplete;
    const submitDisabledDuringActiveJob = card.shadowRoot!.querySelector<HTMLButtonElement>(
      "[data-testid='submit-button']",
    )!.disabled;
    expect(submitDisabledDuringActiveJob).toBe(true);

    await waitFor(() => card.snapshot.status === "complete");
    await card.updateComplete;

    const evidence = {
      command_types: calls.map((call) => call.type),
      final_status: card.snapshot.status,
      final_layout: card.shadowRoot!.querySelector("article")!.getAttribute("data-layout"),
      chart_image_url_prefix: card
        .shadowRoot!.querySelector<HTMLImageElement>("[data-testid='chart-image']")!
        .getAttribute("src")!
        .slice(0, 24),
      validation_status: card.snapshot.validation.status,
      submit_disabled_during_active_job: submitDisabledDuringActiveJob,
    };
    console.info("CARD_SMOKE_EVIDENCE", JSON.stringify(evidence, null, 2));

    expect(calls).toEqual([
      {
        type: ISOLINEAR_COMMANDS.startJob,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: "real-slice-entry",
        prompt: "Show sensor.upstairs_temperature for the last 24 hours",
      },
      {
        type: ISOLINEAR_COMMANDS.getSnapshot,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: "real-slice-entry",
        job_id: "job-smoke-001",
      },
    ]);
    expect(card.shadowRoot!.querySelector("article")!.getAttribute("data-layout")).toBe("chart-first");
    expect(card.shadowRoot!.querySelector<HTMLImageElement>("[data-testid='chart-image']")!.getAttribute("src")).toBe(
      SERVED_PNG_URL,
    );
    expect(card.snapshot.validation.status).toBe("pass");
  });

  it("keeps polling after a transient snapshot timeout and renders the later PNG chart", async () => {
    const { hass, calls } = createTimeoutThenCompleteHass();
    const card = new IsolinearCard();
    card.snapshotPollIntervalMs = 5;
    document.body.append(card);
    card.setConfig({
      type: "custom:isolinear-card",
      config_entry_id: "real-slice-entry",
      title: "Isolinear Smoke",
    });
    card.hass = hass;
    await card.updateComplete;

    const input = card.shadowRoot!.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")!;
    input.value = "Show sensor.upstairs_temperature for the last 24 hours";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await card.updateComplete;

    const form = card.shadowRoot!.querySelector<HTMLFormElement>("[data-testid='composer']")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));

    await waitFor(() => card.snapshot.status === "complete");
    await card.updateComplete;

    const evidence = {
      command_types: calls.map((call) => call.type),
      final_status: card.snapshot.status,
      failure_code: card.snapshot.failure?.code ?? null,
      chart_image_url_prefix: card
        .shadowRoot!.querySelector<HTMLImageElement>("[data-testid='chart-image']")!
        .getAttribute("src")!
        .slice(0, 24),
    };
    console.info("CARD_TRANSIENT_POLL_EVIDENCE", JSON.stringify(evidence, null, 2));

    expect(calls.map((call) => call.type)).toEqual([
      ISOLINEAR_COMMANDS.startJob,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
    ]);
    expect(card.snapshot.status).toBe("complete");
    expect(card.snapshot.failure).toBeUndefined();
    expect(card.shadowRoot!.querySelector<HTMLImageElement>("[data-testid='chart-image']")!.getAttribute("src")).toBe(
      SERVED_PNG_URL,
    );
  });

  it("keeps polling after repeated Home Assistant timeout wrappers and renders the later PNG chart", async () => {
    const { hass, calls } = createRepeatedHomeAssistantTimeoutThenCompleteHass();
    const card = new IsolinearCard();
    card.snapshotPollIntervalMs = 5;
    document.body.append(card);
    card.setConfig({
      type: "custom:isolinear-card",
      config_entry_id: "real-slice-entry",
      title: "Isolinear Smoke",
    });
    card.hass = hass;
    await card.updateComplete;

    const input = card.shadowRoot!.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")!;
    input.value = "Show sensor.upstairs_temperature for the last 24 hours";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await card.updateComplete;

    const form = card.shadowRoot!.querySelector<HTMLFormElement>("[data-testid='composer']")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));

    await waitFor(() => card.snapshot.status === "complete", 1500);
    await card.updateComplete;

    const evidence = {
      command_types: calls.map((call) => call.type),
      snapshot_poll_count: calls.filter((call) => call.type === ISOLINEAR_COMMANDS.getSnapshot).length,
      final_status: card.snapshot.status,
      failure_code: card.snapshot.failure?.code ?? null,
      chart_image_url_prefix: card
        .shadowRoot!.querySelector<HTMLImageElement>("[data-testid='chart-image']")!
        .getAttribute("src")!
        .slice(0, 24),
    };
    console.info("CARD_REPEATED_HA_TIMEOUT_POLL_EVIDENCE", JSON.stringify(evidence, null, 2));

    expect(calls.map((call) => call.type)).toEqual([
      ISOLINEAR_COMMANDS.startJob,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
      ISOLINEAR_COMMANDS.getSnapshot,
    ]);
    expect(card.snapshot.status).toBe("complete");
    expect(card.snapshot.failure).toBeUndefined();
    expect(card.shadowRoot!.querySelector<HTMLImageElement>("[data-testid='chart-image']")!.getAttribute("src")).toBe(
      SERVED_PNG_URL,
    );
  });

  it("shows a visible failure when snapshot polling receives a terminal Isolinear rejection", async () => {
    const { hass, calls } = createTerminalSnapshotRejectionHass();
    const card = new IsolinearCard();
    card.snapshotPollIntervalMs = 5;
    document.body.append(card);
    card.setConfig({
      type: "custom:isolinear-card",
      config_entry_id: "real-slice-entry",
      title: "Isolinear Smoke",
    });
    card.hass = hass;
    await card.updateComplete;

    const input = card.shadowRoot!.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")!;
    input.value = "Show sensor.upstairs_temperature for the last 24 hours";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await card.updateComplete;

    const form = card.shadowRoot!.querySelector<HTMLFormElement>("[data-testid='composer']")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));

    await waitFor(() => card.snapshot.status === "failed");
    await card.updateComplete;

    expect(calls.map((call) => call.type)).toEqual([
      ISOLINEAR_COMMANDS.startJob,
      ISOLINEAR_COMMANDS.getSnapshot,
    ]);
    console.info(
      "CARD_TERMINAL_POLL_FAILURE_EVIDENCE",
      JSON.stringify(
        {
          command_types: calls.map((call) => call.type),
          final_status: card.snapshot.status,
          failure_code: card.snapshot.failure?.code ?? null,
          failure_message: card.snapshot.failure?.message ?? null,
          failure_details_visible: card.shadowRoot!.querySelector("[data-testid='failure-details']") !== null,
        },
        null,
        2,
      ),
    );
    expect(card.snapshot.failure?.code).toBe("snapshot_poll_failed");
    expect(card.snapshot.failure?.message).toContain("job");
    expect(card.shadowRoot!.querySelector("[data-testid='failure-details']")).not.toBeNull();
  });

  it("shows a visible failure when prompt submission is rejected", async () => {
    const { hass, calls } = createRejectingHass();
    const card = new IsolinearCard();
    document.body.append(card);
    card.setConfig(IsolinearCard.getStubConfig());
    card.hass = hass;
    await card.updateComplete;

    const input = card.shadowRoot!.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")!;
    input.value = "Show sensor.family_room_sensor_temperature";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    await card.updateComplete;

    const form = card.shadowRoot!.querySelector<HTMLFormElement>("[data-testid='composer']")!;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true, composed: true }));

    await waitFor(() => card.snapshot.status === "failed");
    await card.updateComplete;

    expect(calls).toEqual([
      {
        type: ISOLINEAR_COMMANDS.startJob,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: "auto",
        prompt: "Show sensor.family_room_sensor_temperature",
      },
    ]);
    expect(card.snapshot.failure?.code).toBe("job_start_failed");
    expect(card.snapshot.failure?.message).toContain("config entry");
    expect(card.shadowRoot!.querySelector("[data-testid='failure-details']")).not.toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { createIsolinearApi, ISOLINEAR_COMMANDS, ISOLINEAR_WS_VERSION } from "./isolinear-api";
import type { HomeAssistantLike, IsolinearJobSnapshot } from "./types";

const config = {
  type: "custom:isolinear-card" as const,
  config_entry_id: "fake-config-entry",
  title: "Isolinear",
};

function createFakeHass(response: IsolinearJobSnapshot) {
  const calls: Array<Record<string, unknown>> = [];
  const hass: HomeAssistantLike = {
    connection: {
      async sendMessagePromise(message: Record<string, unknown>) {
        calls.push(message);
        return response;
      },
    },
  };

  return { hass, calls };
}

describe("Isolinear Home Assistant WebSocket adapter", () => {
  it("sends a versioned prompt-start command through Home Assistant", async () => {
    const response: IsolinearJobSnapshot = {
      snapshot_id: "planning",
      job_id: "job-001",
      status: "planning",
      prompt: "Compare upstairs and downstairs temperatures",
      state_label: "Planning",
      validation: { status: "pending", summary: "Waiting for validation." },
      warnings: [],
    };
    const { hass, calls } = createFakeHass(response);

    const snapshot = await createIsolinearApi(hass, config).startJob(
      "Compare upstairs and downstairs temperatures",
    );

    expect(snapshot).toBe(response);
    expect(calls).toEqual([
      {
        type: ISOLINEAR_COMMANDS.startJob,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: "fake-config-entry",
        prompt: "Compare upstairs and downstairs temperatures",
      },
    ]);
  });

  it("sends clarification answers without storing semantic memory in the browser", async () => {
    const response: IsolinearJobSnapshot = {
      snapshot_id: "complete",
      job_id: "job-001",
      status: "complete",
      prompt: "Show upstairs temperature",
      state_label: "Complete",
      validation: { status: "pass", summary: "Validation passed." },
      warnings: [],
    };
    const clarification: IsolinearJobSnapshot = {
      snapshot_id: "clarification",
      job_id: "job-001",
      status: "clarification_needed",
      prompt: "Show upstairs temperature",
      state_label: "Clarification needed",
      clarification: {
        question_id: "clarify_upstairs_temperature",
        message: "Average the upstairs sensors?",
        reason: "Multiple approved entities matched.",
        options: [
          {
            option_id: "average_upstairs_temperature",
            label: "Average upstairs sensors",
            description: "Use the approved upstairs sensors as one series.",
            can_remember: true,
          },
        ],
      },
      validation: { status: "blocked", summary: "Waiting for clarification." },
      warnings: ["clarification_required"],
    };
    const { hass, calls } = createFakeHass(response);

    await createIsolinearApi(hass, config).answerClarification(
      clarification,
      "average_upstairs_temperature",
      false,
    );

    expect(calls).toEqual([
      {
        type: ISOLINEAR_COMMANDS.answerClarification,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: "fake-config-entry",
        job_id: "job-001",
        question_id: "clarify_upstairs_temperature",
        option_id: "average_upstairs_temperature",
        remember: false,
      },
    ]);
  });
});

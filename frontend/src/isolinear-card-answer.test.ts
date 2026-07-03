// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from "vitest";
import { IsolinearCard } from "./isolinear-card";
import type { IsolinearJobSnapshot } from "./types";

const PNG_URL = "/api/isolinear/artifacts/answer-001.png";

function completeSnapshot(
  chart: Partial<IsolinearJobSnapshot["chart"]> = {},
): IsolinearJobSnapshot {
  return {
    snapshot_id: "answer-complete",
    job_id: "job-answer-001",
    status: "complete",
    prompt: "Are the upstairs and downstairs temperatures correlated?",
    state_label: "Complete",
    chart: {
      title: "Upstairs vs downstairs temperature",
      image_url: PNG_URL,
      time_range: "Last 24 hours",
      summary: "Upstairs and downstairs temperature over the last day.",
      series: [],
      overlays: [],
      ...chart,
    },
    aliases: [],
    validation: { status: "pass", summary: "ok" },
    warnings: [],
  };
}

async function mount(snapshot: IsolinearJobSnapshot): Promise<IsolinearCard> {
  const card = new IsolinearCard();
  document.body.append(card);
  card.setConfig({ type: "custom:isolinear-card", config_entry_id: "auto", title: "Isolinear" });
  card.snapshot = snapshot;
  await card.updateComplete;
  return card;
}

describe("Isolinear card analysis answer (ADR-0031 tranche 1)", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("renders the grounded answer under the caption", async () => {
    const card = await mount(
      completeSnapshot({ answer_text: "Yes — the correlation coefficient is 0.42." }),
    );
    const answer = card.shadowRoot!.querySelector('[data-testid="analysis-answer"]');
    expect(answer).not.toBeNull();
    expect(answer!.textContent).toBe("Yes — the correlation coefficient is 0.42.");
    // The caption still shows the summary; the answer is an additional line.
    const caption = card.shadowRoot!.querySelector(".result-meta h3")!.textContent!;
    expect(caption).toBe("Upstairs and downstairs temperature over the last day.");
  });

  it("shows no answer line for a chart-only render", async () => {
    const card = await mount(completeSnapshot());
    expect(card.shadowRoot!.querySelector('[data-testid="analysis-answer"]')).toBeNull();
  });

  it("shows no answer line when answer_text is blank", async () => {
    const card = await mount(completeSnapshot({ answer_text: "   " }));
    expect(card.shadowRoot!.querySelector('[data-testid="analysis-answer"]')).toBeNull();
  });
});

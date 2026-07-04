// @vitest-environment happy-dom
// ADR-0031 D8a — answer_verification caveat and withheld-answer rendering.

import { beforeEach, describe, expect, it } from "vitest";
import { IsolinearCard } from "./isolinear-card";
import type { IsolinearJobSnapshot } from "./types";

const PNG_URL = "/api/isolinear/artifacts/grounding-001.png";

function completeSnapshot(
  chart: Partial<IsolinearJobSnapshot["chart"]> = {},
): IsolinearJobSnapshot {
  return {
    snapshot_id: "grounding-complete",
    job_id: "job-grounding-001",
    status: "complete",
    prompt: "Was the upstairs temperature above 22°C for more than 2 hours?",
    state_label: "Complete",
    chart: {
      title: "Upstairs temperature",
      image_url: PNG_URL,
      time_range: "Last 24 hours",
      summary: "Upstairs temperature over the last day.",
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

const TWO_TIER_GUARANTEE =
  "Inside the boundary: value↔data — the integration independently " +
  "recomputed the number from allowlisted history using the claim's own " +
  "recipe; the verdict provably follows from the declared rule at that reference. " +
  "Outside the boundary: internal consistency only (value↔verdict↔rule). " +
  "The caveat means 'not independently reproduced,' not 'probably fine.'";

describe("Isolinear card answer grounding (ADR-0031 D8a)", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  describe("verified answer", () => {
    it("renders the answer without a caveat", async () => {
      const card = await mount(
        completeSnapshot({
          answer_text: "Yes — temperature was above 22°C for 2.4 hours.",
          answer_verification: "verified",
        }),
      );
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="analysis-answer"]')).not.toBeNull();
      expect(shadow.querySelector('[data-testid="analysis-answer"]')!.textContent).toBe(
        "Yes — temperature was above 22°C for 2.4 hours.",
      );
      // No caveat notice for a verified result
      expect(shadow.querySelector('[data-testid="answer-caveat"]')).toBeNull();
    });
  });

  describe("unverified answer (answer present, caveat shown)", () => {
    it("renders the answer and the caveat notice", async () => {
      const card = await mount(
        completeSnapshot({
          answer_text: "Yes — the curve suggests a positive trend.",
          answer_verification: "unverified",
        }),
      );
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="analysis-answer"]')).not.toBeNull();
      expect(shadow.querySelector('[data-testid="answer-caveat"]')).not.toBeNull();
    });

    it("caveat text contains the two-tier guarantee verbatim", async () => {
      const card = await mount(
        completeSnapshot({
          answer_text: "Yes — seems correlated.",
          answer_verification: "unverified",
        }),
      );
      const caveat = card.shadowRoot!.querySelector('[data-testid="answer-caveat"]')!;
      expect(caveat.textContent).toContain(TWO_TIER_GUARANTEE);
    });

    it("does not show the withheld message when answer_text is present", async () => {
      const card = await mount(
        completeSnapshot({
          answer_text: "Yes — above average.",
          answer_verification: "unverified",
        }),
      );
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="analysis-answer-withheld"]')).toBeNull();
    });
  });

  describe("withheld answer (contradicted on exhaustion)", () => {
    it("renders the withheld message instead of the answer", async () => {
      const card = await mount(
        completeSnapshot({
          // No answer_text (withheld by the integration)
          answer_verification: "unverified",
        }),
      );
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="analysis-answer-withheld"]')).not.toBeNull();
      expect(
        shadow.querySelector('[data-testid="analysis-answer-withheld"]')!.textContent,
      ).toContain("could not produce a verifiable answer");
    });

    it("also renders the caveat alongside the withheld message", async () => {
      const card = await mount(
        completeSnapshot({ answer_verification: "unverified" }),
      );
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="answer-caveat"]')).not.toBeNull();
    });

    it("does not render the analysis-answer element", async () => {
      const card = await mount(
        completeSnapshot({ answer_verification: "unverified" }),
      );
      expect(
        card.shadowRoot!.querySelector('[data-testid="analysis-answer"]'),
      ).toBeNull();
    });
  });

  describe("no grounding context (chart-only / Pillow path)", () => {
    it("shows no answer elements when neither answer_text nor verification is set", async () => {
      const card = await mount(completeSnapshot());
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="analysis-answer"]')).toBeNull();
      expect(shadow.querySelector('[data-testid="answer-caveat"]')).toBeNull();
      expect(shadow.querySelector('[data-testid="analysis-answer-withheld"]')).toBeNull();
    });

    it("shows no answer line for blank answer_text with no verification", async () => {
      const card = await mount(completeSnapshot({ answer_text: "   " }));
      const shadow = card.shadowRoot!;
      expect(shadow.querySelector('[data-testid="analysis-answer"]')).toBeNull();
      expect(shadow.querySelector('[data-testid="answer-caveat"]')).toBeNull();
    });
  });
});

// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from "vitest";
import { IsolinearCard } from "./isolinear-card";
import type { IsolinearJobSnapshot } from "./types";

const PNG_URL = "/api/isolinear/artifacts/legend-001.png";

function completeSnapshotWithLegend(
  overrides: Partial<IsolinearJobSnapshot["chart"]> = {},
  rest: Partial<IsolinearJobSnapshot> = {},
): IsolinearJobSnapshot {
  return {
    snapshot_id: "legend-complete",
    job_id: "job-legend-001",
    status: "complete",
    prompt: "Show the family room temperature and when the AC was running",
    state_label: "Complete",
    chart: {
      title: "Temperature History",
      image_url: PNG_URL,
      time_range: "Yesterday",
      summary: "Family room temperature with AC running overlaid.",
      series: [],
      overlays: [],
      legend: [
        {
          label: "Family Room Temperature",
          entity_id: "sensor.family_room_temperature",
          color: "#1f77b4",
          kind: "series",
        },
        {
          label: "AC running",
          entity_id: "climate.kitchen_ecobee",
          color: "#b8d4ee",
          kind: "overlay",
          states: [
            { label: "cooling", color: "#b8d4ee" },
            { label: "heating", color: "#ffcf9e" },
          ],
        },
      ],
      ...overrides,
    },
    aliases: [],
    validation: { status: "pass", summary: "ok" },
    warnings: [],
    ...rest,
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

describe("Isolinear card legend (ADR-0027)", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("uses the model summary as the caption, not the prompt", async () => {
    const card = await mount(completeSnapshotWithLegend());
    const caption = card.shadowRoot!.querySelector(".result-meta h3")!.textContent!;
    expect(caption).toBe("Family room temperature with AC running overlaid.");
    expect(caption).not.toContain("Show the family room");
  });

  it("falls back to the title when there is no summary", async () => {
    const card = await mount(completeSnapshotWithLegend({ summary: undefined }));
    const caption = card.shadowRoot!.querySelector(".result-meta h3")!.textContent!;
    expect(caption).toBe("Temperature History");
  });

  it("renders a Legend section with a swatch per row", async () => {
    const card = await mount(completeSnapshotWithLegend());
    const summary = card.shadowRoot!.querySelector(".legend > summary")!.textContent!;
    expect(summary).toContain("Legend");
    const rows = card.shadowRoot!.querySelectorAll(".legend-row");
    expect(rows.length).toBe(2);
    // One swatch per row summary (child-state swatches live in the disclosure).
    const swatches = card.shadowRoot!.querySelectorAll(".legend-row > details > summary .swatch");
    expect(swatches.length).toBe(2);
  });

  it("reveals the entity id inside the row disclosure", async () => {
    const card = await mount(completeSnapshotWithLegend());
    const entity = card.shadowRoot!.querySelector(".legend-row .legend-entity")!.textContent!;
    expect(entity).toBe("sensor.family_room_temperature");
  });

  it("gives an overlay row a split swatch and per-state children", async () => {
    const card = await mount(completeSnapshotWithLegend());
    const overlayRow = card.shadowRoot!.querySelectorAll(".legend-row")[1]!;
    const swatchStyle = overlayRow.querySelector<HTMLElement>(".swatch")!.getAttribute("style")!;
    expect(swatchStyle).toContain("linear-gradient");
    const states = overlayRow.querySelectorAll(".legend-states li");
    expect(states.length).toBe(2);
    expect(overlayRow.textContent).toContain("cooling");
    expect(overlayRow.textContent).toContain("heating");
  });

  it("gives a computed row a dashed swatch and a computed tag, no state children", async () => {
    // spec card-level-legend-codegen C5: a computed series (mean/delta/deviation)
    // reads distinctly from a solid raw-sensor row and a shaded overlay row.
    const card = await mount(
      completeSnapshotWithLegend({
        legend: [
          { label: "Kitchen Temperature", entity_id: "sensor.kitchen_temperature", color: "#1f77b4", kind: "series" },
          { label: "Basement Temperature", entity_id: "sensor.basement_temperature", color: "#ff7f0e", kind: "series" },
          { label: "Average", entity_id: "sensor.kitchen_temperature", color: "#2ca02c", kind: "computed" },
        ],
      }),
    );
    const rows = card.shadowRoot!.querySelectorAll(".legend-row");
    expect(rows.length).toBe(3);
    const computedRow = rows[2]!;
    // A "computed" tag (not "overlay").
    const tag = computedRow.querySelector(".legend-tag-computed")!;
    expect(tag).not.toBeNull();
    expect(tag.textContent!.toLowerCase()).toContain("computed");
    expect(computedRow.textContent!.toLowerCase()).not.toContain("overlay");
    // A hollow, dashed-outline swatch echoing the dashed line.
    const swatchStyle = computedRow.querySelector<HTMLElement>(".swatch")!.getAttribute("style")!;
    expect(swatchStyle).toContain("dashed");
    expect(swatchStyle).toContain("#2ca02c");
    // A computed series is a line, not a band — no per-state children.
    expect(computedRow.querySelectorAll(".legend-states li").length).toBe(0);
    // The plain series rows carry no tag.
    expect(rows[0]!.querySelector(".legend-tag")).toBeNull();
  });

  it("shows a matched alias inside its row's disclosure", async () => {
    const card = await mount(
      completeSnapshotWithLegend({}, {
        aliases: [
          { name: "air conditioning", meaning: "climate.kitchen_ecobee (entity)", entity_id: "climate.kitchen_ecobee" },
        ],
      }),
    );
    const overlayRow = card.shadowRoot!.querySelectorAll(".legend-row")[1]!;
    expect(overlayRow.querySelector(".legend-alias")!.textContent).toContain("air conditioning");
    // The series row (different entity) shows no alias.
    const seriesRow = card.shadowRoot!.querySelectorAll(".legend-row")[0]!;
    expect(seriesRow.querySelector(".legend-alias")).toBeNull();
  });

  it("renders no Legend section when the legend is absent", async () => {
    const card = await mount(completeSnapshotWithLegend({ legend: undefined }));
    expect(card.shadowRoot!.querySelector(".legend")).toBeNull();
    // Caption still renders; the card does not error.
    expect(card.shadowRoot!.querySelector(".result-meta h3")).not.toBeNull();
  });

  it("surfaces the Pillow fallback notice when a fallback reason is present (ADR-0030)", async () => {
    const card = await mount(
      completeSnapshotWithLegend({ render_path: "pillow", render_fallback_reason: "unsafe_code" }),
    );
    const notice = card.shadowRoot!.querySelector('[data-testid="render-fallback-notice"]')!;
    expect(notice.textContent).toContain("unsafe_code");
  });

  it("shows actionable guidance (not a raw code) for a context-overflow fallback", async () => {
    const card = await mount(
      completeSnapshotWithLegend({
        render_path: "pillow",
        render_fallback_reason: "codegen_context_overflow",
      }),
    );
    const notice = card.shadowRoot!.querySelector('[data-testid="render-fallback-notice"]')!;
    expect(notice.textContent).toContain("context window");
    expect(notice.textContent).toContain("num_ctx");
    // The raw code is not shown as the message body.
    expect(notice.textContent).not.toContain("unavailable: codegen_context_overflow");
  });

  it("shows no fallback notice for a codegen render or an explicit pillow choice", async () => {
    const codegenCard = await mount(completeSnapshotWithLegend({ render_path: "codegen" }));
    expect(codegenCard.shadowRoot!.querySelector('[data-testid="render-fallback-notice"]')).toBeNull();
    document.body.innerHTML = "";
    const pillowCard = await mount(completeSnapshotWithLegend({ render_path: "pillow" }));
    expect(pillowCard.shadowRoot!.querySelector('[data-testid="render-fallback-notice"]')).toBeNull();
  });

  it("never shows a raw entity-id as the primary label", async () => {
    const card = await mount(
      completeSnapshotWithLegend({
        legend: [
          { label: "sensor.attic_temp", entity_id: "sensor.attic_temp", color: "#1f77b4", kind: "series" },
        ],
      }),
    );
    const label = card.shadowRoot!.querySelector(".legend-label")!.textContent!;
    expect(label).toBe("attic temp");
  });
});

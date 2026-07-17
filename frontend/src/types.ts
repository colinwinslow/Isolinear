export type IsolinearJobStatus =
  | "idle"
  | "planning"
  | "clarification_needed"
  | "fetching_history"
  | "rendering"
  | "validating"
  | "complete"
  | "failed";

export interface IsolinearCardConfig {
  type: "custom:isolinear-card";
  config_entry_id: string;
  title?: string;
  density?: "comfortable" | "compact";
  render_preference?: "trusted" | "advanced";
}

export interface IsolinearLegendState {
  label: string;
  color: string;
}

export interface IsolinearLegendItem {
  label: string;
  entity_id: string;
  color: string;
  kind: "series" | "overlay" | "computed";
  states?: IsolinearLegendState[];
}

export interface IsolinearValidationSummary {
  status: string;
  summary: string;
  checks?: Array<{
    name: string;
    status: string;
  }>;
}

export interface IsolinearClarificationOption {
  option_id: string;
  label: string;
  description: string;
  can_remember: boolean;
}

export interface IsolinearJobSnapshot {
  snapshot_id: string;
  job_id: string | null;
  status: IsolinearJobStatus;
  prompt: string;
  state_label: string;
  message?: string;
  progress?: {
    stage: string;
    message: string;
    // ADR-0025: ephemeral, sanitized, length-capped live model reasoning shown
    // in the chart slot during the planning wait; never present on a
    // complete/failed snapshot.
    reasoning?: string;
  };
  clarification?: {
    question_id: string;
    message: string;
    reason: string;
    options: IsolinearClarificationOption[];
  };
  chart?: {
    title: string;
    image_url: string;
    time_range: string;
    summary?: string;
    // ADR-0031 tranche 1: grounded model-authored analysis answer, computed in
    // the sandbox and rendered under the caption. Absent for chart-only renders.
    answer_text?: string;
    series: Array<{
      series_id: string;
      label: string;
      entity_id: string;
    }>;
    overlays: Array<{
      overlay_id: string;
      label: string;
      entity_id: string;
    }>;
    // ADR-0027: renderer color manifest the card renders as the legend.
    legend?: IsolinearLegendItem[];
    // ADR-0031 D8a: grounding check result. 'verified' = value reproduced from
    // data; 'unverified' = internal consistency only or metric outside registry.
    // A withheld answer is absent answer_text with answer_verification 'unverified'.
    answer_verification?: "verified" | "unverified";
    // ADR-0030: how the chart was rendered; render_fallback_reason is present
    // when the trusted Pillow renderer completed the job because codegen
    // could not (fallback surfaced, never silent).
    render_path?: "codegen" | "pillow";
    render_fallback_reason?: string;
  };
  entities?: Array<{
    entity_id: string;
    label: string;
  }>;
  aliases?: Array<{
    name: string;
    meaning: string;
    entity_id?: string;
  }>;
  failure?: {
    stage: string;
    code: string;
    message: string;
  };
  retry_allowed?: boolean;
  validation: IsolinearValidationSummary;
  warnings: string[];
}

export interface HomeAssistantLike {
  connection?: {
    sendMessagePromise(message: Record<string, unknown>): Promise<IsolinearJobSnapshot>;
    subscribeMessage?(
      callback: (message: IsolinearJobSnapshot) => void,
      message: Record<string, unknown>,
    ): Promise<() => void | Promise<void>>;
  };
  isolinearSnapshot?: IsolinearJobSnapshot;
}

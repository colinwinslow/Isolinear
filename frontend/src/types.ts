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
  };
  entities?: Array<{
    entity_id: string;
    label: string;
  }>;
  aliases?: Array<{
    name: string;
    meaning: string;
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

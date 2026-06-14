import { LitElement, css, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { createIsolinearApi } from "./isolinear-api";
import type {
  HomeAssistantLike,
  IsolinearCardConfig,
  IsolinearClarificationOption,
  IsolinearJobSnapshot,
} from "./types";

declare global {
  interface Window {
    customCards?: Array<Record<string, unknown>>;
  }
}

const IDLE_SNAPSHOT: IsolinearJobSnapshot = {
  snapshot_id: "default-idle",
  job_id: null,
  status: "idle",
  prompt: "",
  state_label: "Idle",
  message: "Ready for an approved Home Assistant history question.",
  validation: {
    status: "not_run",
    summary: "Waiting for prompt.",
  },
  warnings: [],
};

const ACTIVE_JOB_STATUSES = new Set<IsolinearJobSnapshot["status"]>([
  "planning",
  "fetching_history",
  "rendering",
  "validating",
]);

const SNAPSHOT_POLL_INTERVAL_MS = 1000;

function validateConfig(config: Partial<IsolinearCardConfig> | undefined): IsolinearCardConfig {
  if (!config || config.type !== "custom:isolinear-card") {
    throw new Error("Isolinear card config requires type custom:isolinear-card.");
  }
  if (typeof config.config_entry_id !== "string" || config.config_entry_id.trim() === "") {
    throw new Error("Isolinear card config requires config_entry_id.");
  }

  return {
    type: "custom:isolinear-card",
    config_entry_id: config.config_entry_id,
    title: config.title ?? "Isolinear",
    density: config.density ?? "comfortable",
    render_preference: config.render_preference ?? "trusted",
  };
}

function statusLayout(status: IsolinearJobSnapshot["status"]): string {
  if (status === "idle") {
    return "prompt-first";
  }
  if (status === "complete") {
    return "chart-first";
  }
  return status;
}

@customElement("isolinear-card")
export class IsolinearCard extends LitElement {
  @property({ attribute: false })
  public hass?: HomeAssistantLike;

  @state()
  public snapshot: IsolinearJobSnapshot = IDLE_SNAPSHOT;

  @state()
  private config?: IsolinearCardConfig;

  @state()
  private prompt = "";

  public snapshotPollIntervalMs = SNAPSHOT_POLL_INTERVAL_MS;

  private pollTimer?: number;
  private pollGeneration = 0;

  public static getConfigElement(): HTMLElement {
    return document.createElement("isolinear-card-editor");
  }

  public static getStubConfig(): IsolinearCardConfig {
    return {
      type: "custom:isolinear-card",
      config_entry_id: "fake-config-entry",
      title: "Isolinear",
    };
  }

  public setConfig(config: Partial<IsolinearCardConfig>): void {
    this.config = validateConfig(config);
  }

  public getCardSize(): number {
    return this.snapshot.status === "complete" ? 6 : 4;
  }

  public getGridOptions(): Record<string, number> {
    return {
      columns: 12,
      rows: this.snapshot.status === "complete" ? 8 : 5,
      min_columns: 6,
      min_rows: 4,
    };
  }

  public disconnectedCallback(): void {
    super.disconnectedCallback();
    this.cancelSnapshotPolling();
  }

  protected updated(changed: Map<string, unknown>): void {
    if (changed.has("hass") && this.hass?.isolinearSnapshot) {
      this.snapshot = this.hass.isolinearSnapshot;
    }
  }

  protected render() {
    const config = this.config;
    const snapshot = this.snapshot;
    const busy = ACTIVE_JOB_STATUSES.has(snapshot.status);

    return html`
      <article class="card" data-layout=${statusLayout(snapshot.status)}>
        <header class="header">
          <div>
            <p class="eyebrow">Isolinear</p>
            <h2>${config?.title ?? "Isolinear"}</h2>
          </div>
          <span class="state" data-testid="job-state">${snapshot.state_label}</span>
        </header>

        <section class="main" data-testid="main-surface">
          ${this.renderMain(snapshot)}
        </section>

        <form class="composer" data-testid="composer" @submit=${this.submitPrompt}>
          <textarea
            data-testid="prompt-input"
            .value=${this.prompt}
            ?disabled=${busy}
            rows=${snapshot.status === "complete" ? 1 : 3}
            placeholder="Ask about approved Home Assistant history"
            @input=${this.updatePrompt}
          ></textarea>
          <button data-testid="submit-button" type="submit" ?disabled=${busy || !this.prompt.trim()}>
            Ask
          </button>
        </form>
      </article>
    `;
  }

  private renderMain(snapshot: IsolinearJobSnapshot) {
    if (snapshot.status === "idle") {
      return html`
        <section class="idle">
          <p>${snapshot.message}</p>
          ${this.renderValidation(snapshot)}
        </section>
      `;
    }

    if (snapshot.status === "planning") {
      return html`
        <section class="active">
          <h3>${snapshot.progress?.stage ?? "Planning"}</h3>
          <p>${snapshot.progress?.message}</p>
          ${this.renderValidation(snapshot)}
        </section>
      `;
    }

    if (snapshot.status === "clarification_needed") {
      return this.renderClarification(snapshot);
    }

    if (snapshot.status === "complete") {
      return html`
        <section class="result">
          <img data-testid="chart-image" src=${snapshot.chart?.image_url ?? ""} alt=${snapshot.chart?.title ?? "Generated chart"}>
          <div class="result-meta">
            <h3>${snapshot.chart?.title}</h3>
            <p>${snapshot.chart?.time_range}</p>
            ${this.renderEntityDisclosure(snapshot)}
            ${this.renderValidation(snapshot)}
          </div>
        </section>
      `;
    }

    return html`
      <section class="failure" data-testid="failure-details">
        <h3>${snapshot.failure?.stage ?? "Failed"}</h3>
        <p>${snapshot.failure?.message}</p>
        <p class="code">${snapshot.failure?.code}</p>
        <button type="button" data-testid="retry-button" ?disabled=${!snapshot.retry_allowed} @click=${this.retryJob}>Retry</button>
        <button type="button" data-testid="revise-button" @click=${this.focusPrompt}>Revise</button>
        ${this.renderValidation(snapshot)}
      </section>
    `;
  }

  private renderClarification(snapshot: IsolinearJobSnapshot) {
    const question = snapshot.clarification;
    if (!question) {
      return nothing;
    }

    return html`
      <section class="clarification" data-testid="clarification-panel">
        <h3>${question.message}</h3>
        <p>${question.reason}</p>
        ${question.options.map((option) => this.renderClarificationOption(snapshot, option))}
        ${this.renderValidation(snapshot)}
      </section>
    `;
  }

  private renderClarificationOption(
    snapshot: IsolinearJobSnapshot,
    option: IsolinearClarificationOption,
  ) {
    return html`
      <div class="choice">
        <div>
          <strong>${option.label}</strong>
          <p>${option.description}</p>
        </div>
        <div class="choice-actions">
          <button type="button" @click=${() => this.answerClarification(snapshot, option, false)}>Use once</button>
          <button type="button" ?disabled=${!option.can_remember} @click=${() => this.answerClarification(snapshot, option, true)}>
            Use and remember
          </button>
        </div>
      </div>
    `;
  }

  private renderEntityDisclosure(snapshot: IsolinearJobSnapshot) {
    return html`
      <details open>
        <summary>Entities and aliases</summary>
        <ul>
          ${(snapshot.entities ?? []).map((entity) => html`<li>${entity.label}: ${entity.entity_id}</li>`)}
          ${(snapshot.aliases ?? []).map((alias) => html`<li>${alias.name}: ${alias.meaning}</li>`)}
        </ul>
      </details>
    `;
  }

  private renderValidation(snapshot: IsolinearJobSnapshot) {
    return html`
      <section class="validation" data-testid="validation-status">
        <strong>${snapshot.validation.status}</strong>
        <span>${snapshot.validation.summary}</span>
      </section>
    `;
  }

  private updatePrompt(event: Event): void {
    this.prompt = (event.target as HTMLTextAreaElement).value;
  }

  private async submitPrompt(event: Event): Promise<void> {
    event.preventDefault();
    if (!this.hass || !this.config || !this.prompt.trim() || ACTIVE_JOB_STATUSES.has(this.snapshot.status)) {
      return;
    }

    this.cancelSnapshotPolling();
    this.snapshot = await createIsolinearApi(this.hass, this.config).startJob(this.prompt.trim());
    this.notifyCallsChanged();
    this.startSnapshotPollingIfActive();
  }

  private async answerClarification(
    snapshot: IsolinearJobSnapshot,
    option: IsolinearClarificationOption,
    remember: boolean,
  ): Promise<void> {
    if (!this.hass || !this.config) {
      return;
    }

    this.snapshot = await createIsolinearApi(this.hass, this.config).answerClarification(
      snapshot,
      option.option_id,
      remember,
    );
    this.notifyCallsChanged();
    this.startSnapshotPollingIfActive();
  }

  private async retryJob(): Promise<void> {
    if (!this.hass || !this.config) {
      return;
    }

    this.cancelSnapshotPolling();
    this.snapshot = await createIsolinearApi(this.hass, this.config).retryJob(this.snapshot);
    this.notifyCallsChanged();
    this.startSnapshotPollingIfActive();
  }

  private focusPrompt(): void {
    this.renderRoot.querySelector<HTMLTextAreaElement>("[data-testid='prompt-input']")?.focus();
  }

  private startSnapshotPollingIfActive(): void {
    if (!this.snapshot.job_id || !ACTIVE_JOB_STATUSES.has(this.snapshot.status)) {
      this.cancelSnapshotPolling();
      return;
    }

    this.cancelSnapshotPolling();
    this.pollGeneration += 1;
    this.scheduleSnapshotPoll(this.pollGeneration);
  }

  private scheduleSnapshotPoll(generation: number): void {
    if (!this.snapshot.job_id || !ACTIVE_JOB_STATUSES.has(this.snapshot.status)) {
      return;
    }

    this.pollTimer = window.setTimeout(() => {
      void this.pollSnapshot(generation);
    }, this.snapshotPollIntervalMs);
  }

  private async pollSnapshot(generation: number): Promise<void> {
    if (
      generation !== this.pollGeneration ||
      !this.hass ||
      !this.config ||
      !this.snapshot.job_id ||
      !ACTIVE_JOB_STATUSES.has(this.snapshot.status)
    ) {
      return;
    }

    this.pollTimer = undefined;

    try {
      this.snapshot = await createIsolinearApi(this.hass, this.config).getSnapshot(this.snapshot.job_id);
      this.notifyCallsChanged();
    } catch (error) {
      this.snapshot = this.snapshotPollingFailure(error);
      this.notifyCallsChanged();
      return;
    }

    if (generation === this.pollGeneration && ACTIVE_JOB_STATUSES.has(this.snapshot.status)) {
      this.scheduleSnapshotPoll(generation);
    }
  }

  private cancelSnapshotPolling(): void {
    this.pollGeneration += 1;
    if (this.pollTimer !== undefined) {
      window.clearTimeout(this.pollTimer);
      this.pollTimer = undefined;
    }
  }

  private snapshotPollingFailure(error: unknown): IsolinearJobSnapshot {
    const message = error instanceof Error ? error.message : "Snapshot polling failed.";

    return {
      snapshot_id: `${this.snapshot.job_id ?? "job"}-dashboard-poll-failed`,
      job_id: this.snapshot.job_id,
      status: "failed",
      prompt: this.snapshot.prompt,
      state_label: "Failed",
      failure: {
        stage: "dashboard_card",
        code: "snapshot_poll_failed",
        message,
      },
      retry_allowed: true,
      validation: {
        status: "fail",
        summary: "The dashboard card could not refresh the job snapshot.",
      },
      warnings: ["snapshot_poll_failed"],
    };
  }

  private notifyCallsChanged(): void {
    this.dispatchEvent(
      new CustomEvent("isolinear-calls-changed", {
        bubbles: true,
        composed: true,
      }),
    );
  }

  static styles = css`
    :host {
      display: block;
      color: var(--primary-text-color, #1d2633);
    }

    .card {
      background: var(--ha-card-background, #ffffff);
      border: 1px solid var(--divider-color, #d8dee8);
      border-radius: var(--ha-card-border-radius, 8px);
      box-shadow: var(--ha-card-box-shadow, 0 1px 2px rgba(15, 23, 42, 0.12));
      display: grid;
      gap: 14px;
      min-height: 360px;
      padding: 16px;
    }

    .card[data-layout="chart-first"] {
      grid-template-rows: auto minmax(280px, 1fr) auto;
      min-height: 560px;
    }

    .header,
    .choice,
    .choice-actions,
    .composer,
    .validation {
      display: flex;
      gap: 10px;
    }

    .header {
      align-items: center;
      justify-content: space-between;
    }

    .eyebrow,
    h2,
    h3,
    p {
      margin: 0;
    }

    .eyebrow,
    .state,
    .code {
      color: var(--secondary-text-color, #596579);
      font-size: 0.8rem;
      text-transform: uppercase;
    }

    h2 {
      font-size: 1.2rem;
    }

    h3 {
      font-size: 1rem;
    }

    .main {
      min-height: 150px;
    }

    .result {
      display: grid;
      gap: 12px;
      grid-template-rows: minmax(260px, 1fr) auto;
      height: 100%;
    }

    .result img {
      background: #f7f9fb;
      border: 1px solid var(--divider-color, #d8dee8);
      border-radius: 6px;
      height: 100%;
      min-height: 260px;
      object-fit: contain;
      width: 100%;
    }

    .result-meta,
    .active,
    .idle,
    .failure,
    .clarification {
      display: grid;
      gap: 10px;
    }

    .choice {
      align-items: center;
      border: 1px solid var(--divider-color, #d8dee8);
      border-radius: 6px;
      justify-content: space-between;
      padding: 10px;
    }

    .choice-actions {
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .composer {
      align-items: stretch;
    }

    textarea {
      border: 1px solid var(--divider-color, #c9d3df);
      border-radius: 6px;
      box-sizing: border-box;
      flex: 1;
      font: inherit;
      min-width: 0;
      padding: 10px;
      resize: vertical;
    }

    button {
      background: var(--primary-color, #2563eb);
      border: 0;
      border-radius: 6px;
      color: var(--text-primary-color, #ffffff);
      cursor: pointer;
      font: inherit;
      min-width: 76px;
      padding: 0 14px;
    }

    button:disabled {
      cursor: default;
      opacity: 0.52;
    }

    .validation {
      align-items: baseline;
      color: var(--secondary-text-color, #596579);
      flex-wrap: wrap;
      font-size: 0.9rem;
    }
  `;
}

@customElement("isolinear-card-editor")
export class IsolinearCardEditor extends LitElement {
  @state()
  private config: IsolinearCardConfig = IsolinearCard.getStubConfig();

  public setConfig(config: IsolinearCardConfig): void {
    this.config = validateConfig(config);
  }

  protected render() {
    return html`
      <label>
        Config entry
        <input .value=${this.config.config_entry_id} @input=${this.updateConfigEntry}>
      </label>
    `;
  }

  private updateConfigEntry(event: Event): void {
    this.config = {
      ...this.config,
      config_entry_id: (event.target as HTMLInputElement).value,
    };
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this.config },
        bubbles: true,
        composed: true,
      }),
    );
  }
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === "isolinear-card")) {
  window.customCards.push({
    type: "isolinear-card",
    name: "Isolinear",
    description: "Ask chart questions about approved Home Assistant entities.",
    preview: true,
  });
}

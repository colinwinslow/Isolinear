import type { HomeAssistantLike, IsolinearCardConfig, IsolinearJobSnapshot } from "./types";

export const ISOLINEAR_WS_VERSION = 1;

export const ISOLINEAR_COMMANDS = {
  startJob: "isolinear/v1/job/start",
  answerClarification: "isolinear/v1/clarification/answer",
  retryJob: "isolinear/v1/job/retry",
  getSnapshot: "isolinear/v1/job/snapshot",
} as const;

export function createIsolinearApi(hass: HomeAssistantLike, config: IsolinearCardConfig) {
  const connection = hass.connection;
  if (!connection || typeof connection.sendMessagePromise !== "function") {
    throw new Error("Isolinear requires a Home Assistant connection.");
  }

  return {
    startJob(prompt: string): Promise<IsolinearJobSnapshot> {
      return connection.sendMessagePromise({
        type: ISOLINEAR_COMMANDS.startJob,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: config.config_entry_id,
        prompt,
      });
    },

    answerClarification(
      snapshot: IsolinearJobSnapshot,
      optionId: string,
      remember: boolean,
    ): Promise<IsolinearJobSnapshot> {
      if (!snapshot.job_id || !snapshot.clarification) {
        throw new Error("Clarification answer requires an active clarification snapshot.");
      }

      return connection.sendMessagePromise({
        type: ISOLINEAR_COMMANDS.answerClarification,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: config.config_entry_id,
        job_id: snapshot.job_id,
        question_id: snapshot.clarification.question_id,
        option_id: optionId,
        remember,
      });
    },

    retryJob(snapshot: IsolinearJobSnapshot): Promise<IsolinearJobSnapshot> {
      if (!snapshot.job_id) {
        throw new Error("Retry requires a job id.");
      }

      return connection.sendMessagePromise({
        type: ISOLINEAR_COMMANDS.retryJob,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: config.config_entry_id,
        job_id: snapshot.job_id,
      });
    },

    getSnapshot(jobId: string): Promise<IsolinearJobSnapshot> {
      return connection.sendMessagePromise({
        type: ISOLINEAR_COMMANDS.getSnapshot,
        version: ISOLINEAR_WS_VERSION,
        config_entry_id: config.config_entry_id,
        job_id: jobId,
      });
    },
  };
}

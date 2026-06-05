export async function loadFixtureSnapshots() {
  const response = await fetch("../fixtures/job-snapshots.json");
  if (!response.ok) {
    throw new Error(`Unable to load fixture snapshots: ${response.status}`);
  }
  return response.json();
}

export function createFakeHass({ snapshots, initialState = "idle" }) {
  const calls = [];
  let currentSnapshot = snapshots[initialState];

  return {
    language: "en",
    themes: { darkMode: false },
    connection: {
      async sendMessagePromise(message) {
        calls.push(message);
        if (message.type === "isolinear/v1/job/start") {
          currentSnapshot = snapshots.planning;
          return currentSnapshot;
        }
        if (message.type === "isolinear/v1/clarification/answer") {
          currentSnapshot = snapshots.complete;
          return currentSnapshot;
        }
        if (message.type === "isolinear/v1/job/retry") {
          currentSnapshot = snapshots.planning;
          return currentSnapshot;
        }
        if (message.type === "isolinear/v1/job/snapshot") {
          return currentSnapshot;
        }
        throw new Error(`Unexpected Isolinear command: ${message.type}`);
      },
    },
    get isolinearCalls() {
      return calls;
    },
    get isolinearSnapshot() {
      return currentSnapshot;
    },
    setIsolinearSnapshot(snapshot) {
      currentSnapshot = snapshot;
    },
  };
}

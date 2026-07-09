import { describe, it, expect, beforeEach } from "vitest";
import { act } from "@testing-library/react";
import { useStudio } from "@/lib/earendel/store";

// Reset the Zustand store between tests so each test starts from initial state.
beforeEach(() => {
  act(() => {
    useStudio.setState({
      entered: false,
      authOpen: false,
      user: null,
      view: "dashboard",
      selectedActionId: null,
      selectedConnectorId: null,
      selectedExecutionId: null,
      selectedRecordingId: null,
    });
  });
});

describe("useStudio — initial state", () => {
  it("starts on the dashboard view", () => {
    expect(useStudio.getState().view).toBe("dashboard");
  });

  it("starts with entered=false", () => {
    expect(useStudio.getState().entered).toBe(false);
  });

  it("starts with selectedActionId=null", () => {
    expect(useStudio.getState().selectedActionId).toBeNull();
  });

  it("starts with selectedConnectorId=null", () => {
    expect(useStudio.getState().selectedConnectorId).toBeNull();
  });

  it("starts with selectedExecutionId=null", () => {
    expect(useStudio.getState().selectedExecutionId).toBeNull();
  });

  it("starts with selectedRecordingId=null", () => {
    expect(useStudio.getState().selectedRecordingId).toBeNull();
  });

  it("starts with authOpen=false", () => {
    expect(useStudio.getState().authOpen).toBe(false);
  });
});

describe("useStudio — setView", () => {
  it("changes view to 'actions'", () => {
    act(() => useStudio.getState().setView("actions"));
    expect(useStudio.getState().view).toBe("actions");
  });

  it("changes view to 'monitoring'", () => {
    act(() => useStudio.getState().setView("monitoring"));
    expect(useStudio.getState().view).toBe("monitoring");
  });

  it("changes view to 'discovery' (TRACK-6)", () => {
    act(() => useStudio.getState().setView("discovery"));
    expect(useStudio.getState().view).toBe("discovery");
  });

  it("changes view to 'repair_kb' (TRACK-6)", () => {
    act(() => useStudio.getState().setView("repair_kb"));
    expect(useStudio.getState().view).toBe("repair_kb");
  });
});

describe("useStudio — openAction", () => {
  it("sets view to 'action-detail' and selectedActionId", () => {
    act(() => useStudio.getState().openAction("act_123"));
    const s = useStudio.getState();
    expect(s.view).toBe("action-detail");
    expect(s.selectedActionId).toBe("act_123");
  });
});

describe("useStudio — openConnector", () => {
  it("sets view to 'connector-detail' and selectedConnectorId", () => {
    act(() => useStudio.getState().openConnector("conn_123"));
    const s = useStudio.getState();
    expect(s.view).toBe("connector-detail");
    expect(s.selectedConnectorId).toBe("conn_123");
  });
});

describe("useStudio — openExecution", () => {
  it("sets view to 'executions' and selectedExecutionId", () => {
    act(() => useStudio.getState().openExecution("exe_123"));
    const s = useStudio.getState();
    expect(s.view).toBe("executions");
    expect(s.selectedExecutionId).toBe("exe_123");
  });
});

describe("useStudio — openRecording", () => {
  it("sets view to 'recording-detail' and selectedRecordingId", () => {
    act(() => useStudio.getState().openRecording("rec_123"));
    const s = useStudio.getState();
    expect(s.view).toBe("recording-detail");
    expect(s.selectedRecordingId).toBe("rec_123");
  });
});

describe("useStudio — setEntered", () => {
  it("sets entered to true", () => {
    act(() => useStudio.getState().setEntered(true));
    expect(useStudio.getState().entered).toBe(true);
  });

  it("can reset entered to false", () => {
    act(() => useStudio.getState().setEntered(true));
    act(() => useStudio.getState().setEntered(false));
    expect(useStudio.getState().entered).toBe(false);
  });
});

describe("useStudio — setAuthOpen", () => {
  it("sets authOpen to true", () => {
    act(() => useStudio.getState().setAuthOpen(true));
    expect(useStudio.getState().authOpen).toBe(true);
  });
});

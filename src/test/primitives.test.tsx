import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  StatCard,
  StatusDot,
  AdapterChip,
  RiskBadge,
  EmptyState,
  CodeBlock,
  Kbd,
} from "@/components/earendel/primitives";

// Hold the spy reference so tests can assert against it directly. jsdom doesn't
// implement the async clipboard API, so we install a stub before each test and
// restore afterwards.
let writeTextSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  writeTextSpy = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: writeTextSpy },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("StatCard", () => {
  it("renders label and value", () => {
    render(<StatCard icon="dashboard" label="Actions" value={42} />);
    expect(screen.getByText("Actions")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("shows loading state instead of value", () => {
    render(
      <StatCard icon="dashboard" label="Actions" value={42} loading />
    );
    expect(screen.getByText("Actions")).toBeInTheDocument();
    expect(screen.queryByText("42")).not.toBeInTheDocument();
    expect(screen.getByText("…")).toBeInTheDocument();
  });

  it("shows delta with up trend arrow", () => {
    render(
      <StatCard
        icon="dashboard"
        label="Executions"
        value={100}
        delta="+12%"
        trend="up"
      />
    );
    expect(screen.getByText(/▲/)).toHaveTextContent("▲ +12%");
  });

  it("shows delta with down trend arrow", () => {
    render(
      <StatCard
        icon="dashboard"
        label="Failures"
        value={3}
        delta="-2"
        trend="down"
      />
    );
    expect(screen.getByText(/▼/)).toHaveTextContent("▼ -2");
  });

  it("shows delta with flat trend marker", () => {
    render(
      <StatCard
        icon="dashboard"
        label="MTTR"
        value="1.2h"
        delta="0%"
        trend="flat"
      />
    );
    expect(screen.getByText(/•/)).toHaveTextContent("• 0%");
  });

  it("does not render delta when not provided", () => {
    render(<StatCard icon="dashboard" label="Plain" value={5} />);
    expect(screen.queryByText(/▲|▼|•/)).not.toBeInTheDocument();
  });
});

describe("StatusDot", () => {
  it.each([
    ["draft", "Draft"],
    ["testing", "Testing"],
    ["published", "Published"],
    ["degraded", "Degraded"],
    ["broken", "Broken"],
    ["queued", "Queued"],
    ["running", "Running"],
    ["success", "Success"],
    ["failed", "Failed"],
    ["human_review", "Human review"],
    ["active", "Active"],
    ["paused", "Paused"],
    ["error", "Error"],
  ])("renders label '%s' for status '%s'", (status, label) => {
    const { unmount } = render(<StatusDot status={status as never} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    unmount();
  });
});

describe("AdapterChip", () => {
  it("renders adapter name", () => {
    render(<AdapterChip adapter="api" />);
    expect(screen.getByText("api")).toBeInTheDocument();
  });

  it("humanizes underscores in adapter name", () => {
    render(<AdapterChip adapter="internal_route" />);
    expect(screen.getByText("internal route")).toBeInTheDocument();
  });

  it("shows active state styling when active", () => {
    const { container } = render(<AdapterChip adapter="browser" active />);
    const chip = container.querySelector("span");
    expect(chip?.className).toMatch(/border-primary/);
    expect(chip?.className).toMatch(/bg-primary\/15/);
  });

  it("uses muted styling when not active", () => {
    const { container } = render(<AdapterChip adapter="browser" />);
    const chip = container.querySelector("span");
    expect(chip?.className).toMatch(/border-border/);
    expect(chip?.className).toMatch(/bg-secondary/);
  });

  it("renders bu_browser with a distinct label and cloud styling (TRACK-6)", () => {
    const { container } = render(<AdapterChip adapter="bu_browser" />);
    expect(screen.getByText("BU browser")).toBeInTheDocument();
    // bu_browser uses the chart-1 (purple) palette to signal "optional cloud".
    const chip = container.querySelector("span");
    expect(chip?.className).toMatch(/border-chart-1/);
    expect(chip?.className).toMatch(/text-chart-1/);
  });
});

describe("RiskBadge", () => {
  it.each([
    ["low", /low/],
    ["medium", /medium/],
    ["high", /high/],
    ["critical", /critical/],
  ])("renders level '%s'", (level, matcher) => {
    const { unmount } = render(<RiskBadge level={level as never} />);
    expect(screen.getByText(matcher)).toBeInTheDocument();
    unmount();
  });
});

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState icon="inbox" title="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(
      <EmptyState
        icon="inbox"
        title="Nothing here"
        description="Try creating something"
      />
    );
    expect(screen.getByText("Try creating something")).toBeInTheDocument();
  });

  it("does not render description when omitted", () => {
    render(<EmptyState icon="inbox" title="No description" />);
    expect(
      screen.queryByText("Try creating something")
    ).not.toBeInTheDocument();
  });
});

describe("CodeBlock", () => {
  it("renders the provided code", () => {
    const code = 'console.log("hello")';
    render(<CodeBlock code={code} language="typescript" />);
    expect(screen.getByText(code)).toBeInTheDocument();
  });

  it("renders language label when provided", () => {
    render(<CodeBlock code="x = 1" language="python" />);
    expect(screen.getByText("python")).toBeInTheDocument();
  });

  it("defaults label to 'code' when language omitted", () => {
    render(<CodeBlock code="x = 1" />);
    expect(screen.getByText("code")).toBeInTheDocument();
  });

  it("has a copy button", () => {
    render(<CodeBlock code="x = 1" />);
    expect(
      screen.getByRole("button", { name: /copy code to clipboard/i })
    ).toBeInTheDocument();
  });

  it("copies code to clipboard and shows 'Copied' on click", async () => {
    const code = "to-be-copied";
    render(<CodeBlock code={code} />);
    const btn = screen.getByRole("button", { name: /copy code to clipboard/i });
    fireEvent.click(btn);
    // copy() is async — wait a tick for the await + setState to flush.
    expect(writeTextSpy).toHaveBeenCalledWith(code);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });
});

describe("Kbd", () => {
  it("renders children inside a kbd element", () => {
    const { container } = render(<Kbd>⌘K</Kbd>);
    const kbd = container.querySelector("kbd");
    expect(kbd).not.toBeNull();
    expect(kbd?.textContent).toBe("⌘K");
  });

  it("renders arbitrary children", () => {
    render(<Kbd>Shift</Kbd>);
    expect(screen.getByText("Shift")).toBeInTheDocument();
  });
});

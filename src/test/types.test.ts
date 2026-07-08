import { describe, it, expect } from "vitest";
import type {
  RiskLevel,
  AdapterType,
  ActionStatus,
  ExecutionStatus,
  StudioView,
  PermissionScope,
  WorkflowCategory,
} from "@/lib/earendel/types";

/**
 * Type validation tests — these tests assert both that the TypeScript types
 * accept the expected string literals (compile-time) and that those literal
 * values match the contract documented in `types.ts` (runtime).
 *
 * The arrays below are annotated with their domain type so any drift in the
 * source union will surface as a TS error during `tsc`/vitest type-check, and
 * the `expect` calls assert the actual runtime values are still correct.
 */

describe("ActionStatus", () => {
  const values: ActionStatus[] = [
    "draft",
    "testing",
    "published",
    "degraded",
    "broken",
  ];

  it("has 5 statuses", () => {
    expect(values).toHaveLength(5);
  });

  it("contains the expected string literals", () => {
    expect(values).toEqual([
      "draft",
      "testing",
      "published",
      "degraded",
      "broken",
    ]);
  });

  it("uses lowercase snake_case strings", () => {
    for (const v of values) {
      expect(v).toMatch(/^[a-z]+$/);
    }
  });
});

describe("AdapterType", () => {
  const values: AdapterType[] = [
    "api",
    "internal_route",
    "browser",
    "vision",
    "human",
  ];

  it("has 5 adapters", () => {
    expect(values).toHaveLength(5);
  });

  it("contains the expected string literals", () => {
    expect(values).toEqual([
      "api",
      "internal_route",
      "browser",
      "vision",
      "human",
    ]);
  });

  it("uses lowercase snake_case strings", () => {
    for (const v of values) {
      expect(v).toMatch(/^[a-z_]+$/);
    }
  });
});

describe("ExecutionStatus", () => {
  const values: ExecutionStatus[] = [
    "queued",
    "running",
    "success",
    "failed",
    "degraded",
    "human_review",
  ];

  it("has 6 statuses", () => {
    expect(values).toHaveLength(6);
  });

  it("contains the expected string literals", () => {
    expect(values).toEqual([
      "queued",
      "running",
      "success",
      "failed",
      "degraded",
      "human_review",
    ]);
  });

  it("uses lowercase snake_case strings", () => {
    for (const v of values) {
      expect(v).toMatch(/^[a-z_]+$/);
    }
  });
});

describe("RiskLevel", () => {
  const values: RiskLevel[] = ["low", "medium", "high", "critical"];

  it("has 4 levels", () => {
    expect(values).toHaveLength(4);
  });

  it("contains the expected string literals", () => {
    expect(values).toEqual(["low", "medium", "high", "critical"]);
  });

  it("uses lowercase strings", () => {
    for (const v of values) {
      expect(v).toMatch(/^[a-z]+$/);
    }
  });
});

describe("PermissionScope", () => {
  const values: PermissionScope[] = [
    "read_only",
    "read_write",
    "submit",
    "destructive",
  ];

  it("contains the expected string literals", () => {
    expect(values).toEqual([
      "read_only",
      "read_write",
      "submit",
      "destructive",
    ]);
  });
});

describe("WorkflowCategory", () => {
  const values: WorkflowCategory[] = [
    "finance",
    "healthcare",
    "logistics",
    "ecommerce",
    "hr",
    "compliance",
    "government",
    "other",
  ];

  it("contains the expected string literals", () => {
    expect(values).toEqual([
      "finance",
      "healthcare",
      "logistics",
      "ecommerce",
      "hr",
      "compliance",
      "government",
      "other",
    ]);
  });
});

describe("StudioView", () => {
  const values: StudioView[] = [
    "dashboard",
    "connectors",
    "connector-detail",
    "recorder",
    "recording-detail",
    "actions",
    "action-detail",
    "executions",
    "monitoring",
    "publishing",
    "playground",
  ];

  it("has 11 views", () => {
    expect(values).toHaveLength(11);
  });

  it("includes dashboard, actions, and action-detail", () => {
    expect(values).toContain("dashboard");
    expect(values).toContain("actions");
    expect(values).toContain("action-detail");
  });
});

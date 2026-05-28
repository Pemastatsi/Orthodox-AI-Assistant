import { render, screen, within, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AdminApprovalQueue } from "../components/admin/AdminApprovalQueue";
import { AdminAuditLog } from "../components/admin/AdminAuditLog";
import { AdminFlaggedList } from "../components/admin/AdminFlaggedList";
import { AdminQueryLog } from "../components/admin/AdminQueryLog";
import type {
  AuditEntry,
  Chunk,
  FlaggedQueryWire,
  Page,
  RunTrace,
} from "../lib/schemas";

function runTrace(over: Partial<RunTrace>): RunTrace {
  return {
    runId: "run_abc",
    tenantId: "tn_test",
    userId: "usr_test",
    sessionId: null,
    startedAt: "2026-05-28T10:00:00Z",
    finishedAt: "2026-05-28T10:00:00.250Z",
    cacheHit: false,
    stages: [],
    usage: { servedAnswerCount: 1, freshModelRunCount: 1 },
    finalHandling: "answer",
    finalConfidenceTier: "YELLOW",
    verifierPassed: true,
    evidencePacketRef: null,
    ...over,
  };
}

function page<T>(items: T[]): Page<T> {
  return { items, nextCursor: null };
}

describe("<AdminQueryLog>", () => {
  it("renders one row per trace with confidence pill + duration", () => {
    render(
      <AdminQueryLog
        page={page([
          runTrace({ runId: "run_1", finalConfidenceTier: "GREEN" }),
          runTrace({ runId: "run_2", cacheHit: true, finalConfidenceTier: "RED" }),
        ])}
      />,
    );
    expect(screen.getByText("GREEN")).toBeInTheDocument();
    expect(screen.getByText("RED")).toBeInTheDocument();
    expect(screen.getByText("hit")).toBeInTheDocument();
    expect(screen.getAllByText(/ms$/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders the empty state with no rows", () => {
    render(<AdminQueryLog page={page<RunTrace>([])} />);
    expect(screen.getByText("No query log rows.")).toBeInTheDocument();
  });
});

describe("<AdminFlaggedList>", () => {
  function flagged(over: Partial<FlaggedQueryWire>): FlaggedQueryWire {
    return {
      flaggedQueryId: "flq_1",
      tenantId: "tn_test",
      userId: "usr_test",
      runId: "run_1",
      queryTextRedacted: "I want to [redacted]",
      rawSensitiveLogId: null,
      flagReason: "hard_safety_trigger",
      sensitivityPrimary: "pastoral_advice",
      riskFlags: [],
      createdAt: "2026-05-28T10:00:00Z",
      ...over,
    };
  }

  it("renders self-harm rows with a danger badge", () => {
    render(
      <AdminFlaggedList
        page={page([flagged({ riskFlags: ["self_harm"] })])}
      />,
    );
    expect(screen.getByText("hard safety trigger")).toBeInTheDocument();
  });

  it("renders the View-raw link only when rawSensitiveLogId is non-null", () => {
    render(
      <AdminFlaggedList
        page={page([
          flagged({ flaggedQueryId: "flq_a", rawSensitiveLogId: null }),
          flagged({ flaggedQueryId: "flq_b", rawSensitiveLogId: "rsl_b" }),
        ])}
      />,
    );
    const links = screen.queryAllByText(/View raw/);
    expect(links).toHaveLength(1);
  });
});

describe("<AdminAuditLog>", () => {
  it("renders actor, action, resource columns", () => {
    const entry: AuditEntry = {
      auditId: "aud_1",
      tenantId: "tn_test",
      actorUserId: "usr_admin",
      actorRole: "admin",
      action: "raw_sensitive_view",
      resourceType: "raw_sensitive_log",
      resourceId: "rsl_XYZ",
      occurredAt: "2026-05-28T10:00:00Z",
      details: {},
      ipAddress: "127.0.0.1",
    };
    render(<AdminAuditLog page={page([entry])} />);
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("raw sensitive view")).toBeInTheDocument();
    expect(screen.getByText("rsl_XYZ")).toBeInTheDocument();
  });
});

describe("<AdminApprovalQueue>", () => {
  function chunk(over: Partial<Chunk>): Chunk {
    return {
      chunkId: "chk_1",
      sourceId: "src_1",
      tenantId: "tn_test",
      text: "On prayer, Saint Basil writes…",
      chunkHash: "sha256:" + "0".repeat(64),
      approved: false,
      visibility: "member",
      father: "Basil",
      work: "On Prayer",
      page: "12",
      timestamp: null,
      language: "en",
      reviewNote: null,
      createdAt: "2026-05-28T10:00:00Z",
      ...over,
    };
  }

  it("optimistically marks a chunk as approved when onApprove resolves", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    render(
      <AdminApprovalQueue
        initial={page([chunk({})])}
        onApprove={onApprove}
        onReject={vi.fn()}
        onSetVisibility={vi.fn()}
      />,
    );
    const approve = screen.getByRole("button", { name: /Approve/i });
    fireEvent.click(approve);
    await waitFor(() => expect(onApprove).toHaveBeenCalledWith("chk_1"));
    await waitFor(() => expect(within(screen.getByRole("listitem")).getByText("approved")).toBeInTheDocument());
  });

  it("renders the empty state when no items", () => {
    render(
      <AdminApprovalQueue
        initial={page<Chunk>([])}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onSetVisibility={vi.fn()}
      />,
    );
    expect(screen.getByText("No chunks awaiting review.")).toBeInTheDocument();
  });
});

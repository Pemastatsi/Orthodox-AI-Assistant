import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnswerPanel } from "../components/chat/AnswerPanel";
import { DisputeCard } from "../components/chat/DisputeCard";
import type { Citation, Position, VerifiedResponse } from "../lib/schemas";

function citation(
  id: string,
  title: string,
  father?: string,
): Citation {
  return {
    citationId: id,
    chunkId: `chunk_${id}`,
    sourceId: `src_${id}`,
    title,
    sourceHash: "sha256:" + "0".repeat(64),
    chunkHash: "sha256:" + "1".repeat(64),
    approved: true,
    corpusOrigin: "tenant",
    father: father ?? null,
    work: null,
    page: null,
    timestamp: null,
    quote: null,
  };
}

function makeDisputeResponse(
  positions: Position[],
  citations: Citation[],
): VerifiedResponse {
  return {
    answer:
      "The corpus surfaces two distinct positions on this question; neither is rejected.",
    confidenceTier: "YELLOW",
    handling: "answer",
    citations,
    verification: {
      passed: true,
      checkedAt: "2026-05-28T00:00:00Z",
      verifierVersion: "v1",
      failureReason: null,
    },
    reframing: { wasReframed: false },
    usage: {
      servedAnswerCount: 1,
      freshModelRunCount: 1,
      modelRouteId: "route-1",
    },
    servedFromCache: false,
    schemaVersion: "2026-05-01.1",
    runId: "run_dispute",
    positions,
  };
}

describe("<DisputeCard>", () => {
  const positions: Position[] = [
    {
      name: "Western augustinian framing",
      thesis: "Sin is inherited as guilt from Adam.",
      citationIds: ["c_aug_1"],
      confidenceTier: "GREEN",
    },
    {
      name: "Eastern patristic framing",
      thesis: "Mortality and corruption are inherited; personal guilt is not.",
      citationIds: ["c_basil_1", "c_athan_1"],
      confidenceTier: "YELLOW",
    },
  ];
  const citations = [
    citation("c_aug_1", "Confessions", "Augustine"),
    citation("c_basil_1", "On the Holy Spirit", "Basil"),
    citation("c_athan_1", "On the Incarnation", "Athanasius"),
  ];

  it("renders both positions as labeled columns", () => {
    render(
      <DisputeCard
        response={makeDisputeResponse(positions, citations)}
        positions={positions}
      />,
    );
    const colA = screen.getByLabelText(/Position A: Western augustinian framing/);
    const colB = screen.getByLabelText(/Position B: Eastern patristic framing/);
    expect(colA).toBeInTheDocument();
    expect(colB).toBeInTheDocument();
  });

  it("scopes citations to their column — never aggregates across columns", () => {
    render(
      <DisputeCard
        response={makeDisputeResponse(positions, citations)}
        positions={positions}
      />,
    );
    const colA = screen.getByLabelText(/Position A:/);
    const colB = screen.getByLabelText(/Position B:/);
    expect(within(colA).getByText("Augustine")).toBeInTheDocument();
    expect(within(colA).queryByText("Basil")).toBeNull();
    expect(within(colA).queryByText("Athanasius")).toBeNull();
    expect(within(colB).getByText("Basil")).toBeInTheDocument();
    expect(within(colB).getByText("Athanasius")).toBeInTheDocument();
    expect(within(colB).queryByText("Augustine")).toBeNull();
  });

  it("renders a confidence badge per column with its own tier", () => {
    render(
      <DisputeCard
        response={makeDisputeResponse(positions, citations)}
        positions={positions}
      />,
    );
    const colA = screen.getByLabelText(/Position A:/);
    const colB = screen.getByLabelText(/Position B:/);
    expect(within(colA).getByRole("status")).toHaveAccessibleName(/High confidence/);
    expect(within(colB).getByRole("status")).toHaveAccessibleName(/Moderate confidence/);
  });

  it("renders the contested-area banner so the UI never implies consensus", () => {
    render(
      <DisputeCard
        response={makeDisputeResponse(positions, citations)}
        positions={positions}
      />,
    );
    expect(
      screen.getByText(/Contested area .* both positions remain within Orthodox/),
    ).toBeInTheDocument();
  });

  it("emits onCitationClick when a column's citation chip is clicked", () => {
    const handler = vi.fn();
    render(
      <DisputeCard
        response={makeDisputeResponse(positions, citations)}
        positions={positions}
        onCitationClick={handler}
      />,
    );
    const colB = screen.getByLabelText(/Position B:/);
    within(colB).getByRole("button", { name: /Basil/ }).click();
    expect(handler).toHaveBeenCalledWith("c_basil_1");
  });
});

describe("<AnswerPanel> with positions", () => {
  it("dispatches to <DisputeCard> when response.positions has 2+ entries", () => {
    const positions: Position[] = [
      {
        name: "A",
        thesis: "first",
        citationIds: [],
        confidenceTier: "GREEN",
      },
      {
        name: "B",
        thesis: "second",
        citationIds: [],
        confidenceTier: "GREEN",
      },
    ];
    render(<AnswerPanel response={makeDisputeResponse(positions, [])} />);
    expect(
      screen.getByLabelText("Scholarly dispute — competing positions"),
    ).toBeInTheDocument();
  });

  it("falls back to the normal verified card when positions is absent", () => {
    render(<AnswerPanel response={makeDisputeResponse([], [])} />);
    expect(screen.getByLabelText("Verified answer")).toBeInTheDocument();
  });
});

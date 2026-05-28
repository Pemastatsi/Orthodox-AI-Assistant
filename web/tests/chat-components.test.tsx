import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnswerPanel } from "../components/chat/AnswerPanel";
import { ConfidenceBadge } from "../components/chat/ConfidenceBadge";
import { DisclaimerBanner } from "../components/chat/DisclaimerBanner";
import { ReframingDisclosure } from "../components/chat/ReframingDisclosure";
import type { VerifiedResponse } from "../lib/schemas";

function makeResponse(overrides: Partial<VerifiedResponse> = {}): VerifiedResponse {
  return {
    answer: "Saint Basil writes that prayer requires patience [1].",
    confidenceTier: "YELLOW",
    handling: "answer",
    citations: [
      {
        citationId: "cit_1",
        chunkId: "chunk_1",
        sourceId: "src_1",
        title: "On the Holy Spirit",
        sourceHash: "sha256:" + "0".repeat(64),
        chunkHash: "sha256:" + "1".repeat(64),
        approved: true,
        corpusOrigin: "tenant",
        father: "Basil the Great",
        work: "De Spiritu Sancto",
        page: "12",
        timestamp: null,
        quote: "Pray without ceasing.",
      },
    ],
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
    runId: "run_test",
    ...overrides,
  };
}

describe("<ConfidenceBadge>", () => {
  it("labels each tier and surfaces it as accessible status", () => {
    const { rerender } = render(<ConfidenceBadge tier="GREEN" />);
    expect(screen.getByRole("status")).toHaveAccessibleName(/High confidence \(GREEN\)/);
    rerender(<ConfidenceBadge tier="YELLOW" />);
    expect(screen.getByRole("status")).toHaveAccessibleName(/Moderate confidence \(YELLOW\)/);
    rerender(<ConfidenceBadge tier="RED" />);
    expect(screen.getByRole("status")).toHaveAccessibleName(/Low confidence \(RED\)/);
  });
});

describe("<ReframingDisclosure>", () => {
  it("renders nothing when wasReframed=false", () => {
    const { container } = render(
      <ReframingDisclosure reframing={{ wasReframed: false }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows both original and reframed queries when wasReframed=true", () => {
    render(
      <ReframingDisclosure
        reframing={{
          wasReframed: true,
          originalQuery: "Should I divorce my wife?",
          reframedQuery: "What do the Fathers teach about marriage?",
          disclosureText: "Reframed for teaching-oriented handling.",
        }}
      />,
    );
    expect(screen.getByText("Should I divorce my wife?")).toBeInTheDocument();
    expect(
      screen.getByText("What do the Fathers teach about marriage?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Reframed for teaching-oriented handling."),
    ).toBeInTheDocument();
  });
});

describe("<DisclaimerBanner>", () => {
  it("renders the medical-context copy for medical sensitivity", () => {
    render(<DisclaimerBanner category="medical" />);
    expect(screen.getByText("Medical context")).toBeInTheDocument();
    expect(screen.getByText(/not medical advice/i)).toBeInTheDocument();
  });

  it("falls back to a generic message for unmapped categories", () => {
    render(<DisclaimerBanner category="other_sensitive" />);
    expect(screen.getByText("Sensitive context")).toBeInTheDocument();
  });
});

describe("<AnswerPanel>", () => {
  it("renders the answer and a clickable citation marker for handling='answer'", () => {
    const onCitationClick = vi.fn();
    render(
      <AnswerPanel response={makeResponse()} onCitationClick={onCitationClick} />,
    );
    expect(
      screen.getByText(/Saint Basil writes that prayer requires patience/),
    ).toBeInTheDocument();
    const citationButton = screen.getByRole("button", { name: "Citation 1" });
    citationButton.click();
    expect(onCitationClick).toHaveBeenCalledWith("cit_1");
  });

  it("renders the bounded-fallback text verbatim for handling='block_with_redirect' and hides citations", () => {
    const response = makeResponse({
      handling: "block_with_redirect",
      answer:
        "If you are in immediate danger, please call 988 (Suicide & Crisis Lifeline in the US) or your local emergency services.",
      confidenceTier: "RED",
      citations: [],
    });
    render(<AnswerPanel response={response} />);
    expect(screen.getByText(/please call 988/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Citation/ })).toBeNull();
  });

  it("renders the insufficient-evidence label for handling='insufficient_evidence'", () => {
    const response = makeResponse({
      handling: "insufficient_evidence",
      answer:
        "The approved library does not contain material on this topic. Please consult your priest or a competent teacher rather than asking the library to extrapolate.",
      confidenceTier: "RED",
      citations: [],
    });
    render(<AnswerPanel response={response} />);
    expect(screen.getByText("Insufficient evidence")).toBeInTheDocument();
    expect(
      screen.getByText(/approved library does not contain material/),
    ).toBeInTheDocument();
  });
});

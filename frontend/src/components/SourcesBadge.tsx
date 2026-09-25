/**
 * SourcesBadge component.
 *
 * Renders an expandable badge displaying policy source citations returned
 * by the AI agent. When the agent answers a policy coverage question, it
 * includes references to the specific policy sections used to construct
 * the answer. This component surfaces those references so users can verify
 * the grounding of the response.
 *
 * Interaction:
 *   - Clicking the badge toggles an expandable list of source strings.
 *   - Sources are rendered as individual pill elements for readability.
 */

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface SourcesBadgeProps {
  /** Array of source citation strings from the agent response. */
  sources: string[];
}

export default function SourcesBadge({ sources }: SourcesBadgeProps) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div
      id="sources-badge"
      className="flex flex-col items-start gap-2"
      data-testid="sources-badge"
    >
      <button
        id="sources-toggle"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-insurance-ink-secondary bg-insurance-surface border border-insurance-border hover:bg-insurance-surface-secondary rounded-full transition-colors duration-200"
        data-testid="sources-toggle"
        aria-expanded={expanded}
        aria-controls="sources-list"
      >
        <span data-testid="sources-count">Sources ({sources.length})</span>
        {expanded ? (
          <ChevronUp className="w-3 h-3" data-testid="sources-chevron-up" />
        ) : (
          <ChevronDown className="w-3 h-3" data-testid="sources-chevron-down" />
        )}
      </button>

      {expanded && (
        <div
          id="sources-list"
          className="flex flex-wrap gap-2 mt-1 animate-fade-in"
          data-testid="sources-list"
        >
          {sources.map((source, idx) => (
            <div
              key={idx}
              id={`source-${idx}`}
              className="px-3 py-1.5 bg-insurance-surface border border-insurance-border text-insurance-ink text-xs rounded-lg"
              data-testid={`source-${idx}`}
            >
              {source}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

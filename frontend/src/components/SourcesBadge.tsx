import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface SourcesBadgeProps {
  sources: string[];
}

export default function SourcesBadge({ sources }: SourcesBadgeProps) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-300 bg-gray-800 border border-gray-700 hover:bg-gray-700 rounded-full transition-colors"
      >
        Sources ({sources.length})
        {expanded ? (
          <ChevronUp className="w-3 h-3" />
        ) : (
          <ChevronDown className="w-3 h-3" />
        )}
      </button>

      {expanded && (
        <div className="flex flex-wrap gap-2 mt-1 animate-in slide-in-from-top-1 fade-in duration-200">
          {sources.map((source, idx) => (
            <div
              key={idx}
              className="px-3 py-1.5 bg-gray-700 text-gray-200 text-xs rounded-md border border-gray-600"
            >
              {source}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

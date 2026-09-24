import { ToolCall } from "@/types/chat";
import { ChevronDown } from "lucide-react";

interface ToolCallBadgeProps {
  toolCalls: ToolCall[];
}

export default function ToolCallBadge({ toolCalls }: ToolCallBadgeProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      {toolCalls.map((call, idx) => (
        <ToolCallItem key={idx} call={call} />
      ))}
    </div>
  );
}

function ToolCallItem({ call }: { call: ToolCall }) {
  let badgeColor = "bg-gray-800 border-gray-700 text-gray-300";
  let icon = "";

  if (call.name === "query_policy") {
    badgeColor = "bg-blue-900/40 border-blue-800 text-blue-300";
    icon = "";
  } else if (call.name === "get_claim_status") {
    badgeColor = "bg-amber-900/40 border-amber-800 text-amber-300";
    icon = "";
  } else if (call.name === "submit_claim") {
    badgeColor = "bg-green-900/40 border-green-800 text-green-300";
    icon = "";
  }

  return (
    <details className="group flex flex-col items-start gap-1 w-full">
      <summary
        className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium border rounded-full transition-colors hover:brightness-110 cursor-pointer list-none ${badgeColor}`}
      >
        <span>{icon}</span>
        <span className="font-mono">{call.name}</span>
        <ChevronDown className="w-3 h-3 ml-1 transition-transform group-open:rotate-180" />
      </summary>

      <div className="w-full mt-1 p-3 bg-gray-900 border border-gray-700 rounded-lg text-xs font-mono text-gray-300 overflow-x-auto">
        <div className="mb-2">
          <span className="text-gray-500 select-none">Arguments: </span>
          <pre className="mt-1 text-indigo-300">
            {JSON.stringify(call.arguments, null, 2)}
          </pre>
        </div>
        {call.result && (
          <div>
            <span className="text-gray-500 select-none">Result: </span>
            <pre className="mt-1 text-green-400">
              {JSON.stringify(call.result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </details>
  );
}

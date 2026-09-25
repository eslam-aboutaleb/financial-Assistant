/**
 * ToolCallBadge component.
 *
 * Renders a transparent view of the AI agent's tool invocations during a
 * single assistant message. For standard tools (e.g. ``query_policy``) it
 * shows an expandable details element with arguments and raw JSON result.
 * For richer tools (``get_claim_status``, ``submit_claim``) it renders
 * a purpose-built status card or claim receipt for readability.
 *
 * Design rationale:
 *   - Tool transparency builds user trust by showing exactly what the agent
 *     did to arrive at its answer.
 *   - Rich UIs for claim tools reduce cognitive load compared to raw JSON.
 *   - The details/summary pattern keeps the default view compact.
 */

import { ToolCall } from "@/types/chat";
import { ChevronDown, CheckCircle2, AlertCircle } from "lucide-react";

interface ToolCallBadgeProps {
  /** Array of tool calls made during the generation of an assistant message. */
  toolCalls: ToolCall[];
}

export default function ToolCallBadge({ toolCalls }: ToolCallBadgeProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 mt-4">
      {toolCalls.map((call, idx) => (
        <ToolCallItem key={idx} call={call} index={idx} />
      ))}
    </div>
  );
}

function StatusCard({ result }: { result: any }) {
  if (result?.error) {
    return (
      <div className="bg-insurance-error/10 border border-insurance-error/20 rounded-xl p-4 mt-2">
        <div className="flex items-center space-x-2 text-insurance-error mb-2">
          <AlertCircle className="w-5 h-5" />
          <span className="font-medium">Claim Not Found</span>
        </div>
        <p className="text-sm text-insurance-ink-secondary">{result.error}</p>
      </div>
    );
  }

  if (!result || typeof result !== "object") return null;

  const statusColors: Record<string, string> = {
    Filed: "bg-insurance-info",
    "Under Review": "bg-insurance-warning",
    Approved: "bg-insurance-success",
    Paid: "bg-insurance-success",
    Denied: "bg-insurance-error",
  };

  const color = statusColors[result.status] || "bg-insurance-ink-tertiary";

  return (
    <div className="bg-insurance-surface border border-insurance-border rounded-xl p-5 mt-2 shadow-subtle">
      <div className="flex justify-between items-start mb-4">
        <div>
          <p className="text-xs text-insurance-ink-tertiary uppercase tracking-wider mb-1">
            Claim Reference
          </p>
          <h3 className="text-lg font-mono text-insurance-ink">
            {result.claim_id}
          </h3>
        </div>
        <div
          className={`flex items-center space-x-1.5 px-3 py-1 rounded-full bg-insurance-surface-secondary border border-insurance-border`}
        >
          <div className={`w-2 h-2 rounded-full ${color} animate-pulse`}></div>
          <span className="text-sm font-medium text-insurance-ink">
            {result.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-insurance-ink-tertiary">Type</p>
          <p className="text-insurance-ink font-medium">{result.claim_type}</p>
        </div>
        <div>
          <p className="text-insurance-ink-tertiary">Amount</p>
          <p className="text-insurance-ink font-medium">
            ${(result.amount || 0).toLocaleString()}
          </p>
        </div>
        <div className="col-span-2">
          <p className="text-insurance-ink-tertiary">Filed On</p>
          <p className="text-insurance-ink">
            {new Date(result.filing_date).toLocaleDateString()}
          </p>
        </div>
      </div>
    </div>
  );
}

function ReceiptCard({ result }: { result: any }) {
  if (result?.success === false) {
    return (
      <div className="bg-insurance-error/10 border border-insurance-error/20 rounded-xl p-4 mt-2 text-sm text-insurance-error">
        <AlertCircle className="w-5 h-5 inline mr-2" />
        Failed to submit claim.
      </div>
    );
  }

  return (
    <div className="bg-insurance-success/10 border border-insurance-success/20 rounded-xl p-5 mt-2 shadow-subtle relative overflow-hidden">
      <div className="absolute top-0 right-0 p-4 opacity-10">
        <CheckCircle2 className="w-24 h-24 text-insurance-success" />
      </div>
      <div className="flex items-center space-x-3 mb-4 relative z-10">
        <div className="w-10 h-10 bg-insurance-success/20 rounded-full flex items-center justify-center text-insurance-success">
          <CheckCircle2 className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-lg font-medium text-insurance-ink">
            Claim Submitted Successfully
          </h3>
          <p className="text-sm text-insurance-ink-secondary">
            We&apos;ve received your information
          </p>
        </div>
      </div>

      <div className="bg-insurance-surface/70 rounded-lg p-4 relative z-10 border border-insurance-border">
        <p className="text-xs text-insurance-ink-tertiary uppercase tracking-wider mb-1">
          Your Claim ID
        </p>
        <p className="text-xl font-mono text-insurance-ink mb-4">
          {result.claim_id}
        </p>
        <p className="text-sm text-insurance-ink-tertiary">
          You can use this ID to check the status of your claim at any time.
        </p>
      </div>
    </div>
  );
}

function ToolCallItem({ call, index }: { call: ToolCall; index: number }) {
  let isRichUI = false;

  if (
    call.result &&
    (call.name === "get_claim_status" || call.name === "submit_claim")
  ) {
    isRichUI = true;
  }

  if (isRichUI) {
    if (call.name === "get_claim_status")
      return <StatusCard result={call.result} />;
    if (call.name === "submit_claim")
      return <ReceiptCard result={call.result} />;
  }

  const color =
    call.name === "query_policy"
      ? "bg-insurance-info/10 border-insurance-info/20 text-insurance-info"
      : "bg-insurance-surface border-insurance-border text-insurance-ink";

  return (
    <details className="group flex flex-col items-start gap-1 w-full">
      <summary
        className={`flex w-fit items-center gap-2 px-3 py-1.5 text-xs font-medium border rounded-full transition-colors hover:brightness-95 cursor-pointer list-none ${color}`}
      >
        <span className="font-mono">{call.name}</span>
        <ChevronDown className="w-3 h-3 ml-1 transition-transform group-open:rotate-180" />
      </summary>

      <div className="w-full mt-1 p-3 bg-insurance-surface border border-insurance-border rounded-lg text-xs font-mono text-insurance-ink overflow-x-auto">
        <div className="mb-2">
          <span className="text-insurance-ink-tertiary select-none">
            Arguments:
          </span>
          <pre className="mt-1 text-insurance-ink">
            {JSON.stringify(call.arguments, null, 2)}
          </pre>
        </div>
        {call.result && (
          <div>
            <span className="text-insurance-ink-tertiary select-none">
              Result:
            </span>
            <pre className="mt-1 text-insurance-success">
              {JSON.stringify(call.result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </details>
  );
}

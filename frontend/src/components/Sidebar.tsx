import { Plus, Shield } from "lucide-react";

interface SidebarProps {
  onNewChat: () => void;
}

export default function Sidebar({ onNewChat }: SidebarProps) {
  return (
    <div className="w-full h-full bg-gray-900 border-r border-gray-800 flex flex-col p-2 text-gray-200">
      <div className="flex items-center gap-3 p-3 mb-4 mt-2">
        <Shield className="w-8 h-8 text-indigo-500" />
        <span className="font-semibold text-lg">OmniCare</span>
      </div>

      <button
        onClick={onNewChat}
        className="flex items-center gap-3 p-3 mx-2 rounded-md hover:bg-gray-800 border border-gray-700 transition-colors"
      >
        <Plus className="w-4 h-4" />
        New Chat
      </button>

      <div className="flex-1 overflow-y-auto mt-4 px-2">
        {/* Chat history could go here */}
      </div>

      <div className="p-4 border-t border-gray-800 text-sm text-gray-400">
        Financial Assistant v1.0
      </div>
    </div>
  );
}

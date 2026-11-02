import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Sparkles,
  ChevronDown,
  CheckCircle2,
  HelpCircle,
  RotateCcw,
  X,
  Coins,
  BarChart3,
  TrendingDown,
  Info,
  MessageSquare,
} from "lucide-react";
import { useChat } from "../context/ChatContext";
import { useDataset } from "../context/DatasetContext";

interface FAQCategory {
  title: string;
  icon: React.ReactNode;
  questions: string[];
}

export const Copilot: React.FC = () => {
  const { activeDataset } = useDataset();
  const {
    messages,
    isStreaming,
    sendMessage,
    clearChat,
    activeDetailsIndex,
    setActiveDetailsIndex,
  } = useChat();

  const [input, setInput] = useState("");
  const [showFaqModal, setShowFaqModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat when new messages arrive or stream updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Frequently asked questions categorized
  const faqCategories: FAQCategory[] = [
    {
      title: "Cost Breakdown & Spend",
      icon: <BarChart3 className="w-4 h-4 text-blue-600" />,
      questions: [
        "Which 3 services cost the most in this dataset?",
        "What are my top 5 most expensive services?",
        "What is the total spend across all regions?",
        "What is our daily cost trend?",
        "Break down our cloud costs by region.",
      ],
    },
    {
      title: "Savings & Waste Opportunities",
      icon: <TrendingDown className="w-4 h-4 text-emerald-600" />,
      questions: [
        "What are the top savings ideas?",
        "Show me the top savings ideas for Compute Engine.",
        "How much can we save by fixing idle resources?",
        "What can we save on underused machines?",
        "Show me the highest priority saving recommendation.",
      ],
    },
    {
      title: "Service-Specific Deep Dives",
      icon: <Coins className="w-4 h-4 text-amber-600" />,
      questions: [
        "How much did we spend on Compute Engine?",
        "How much did Cloud SQL cost?",
        "Which region spent the most?",
        "Show me the breakdown of costs by service.",
      ],
    },
  ];

  // Quick prompt pills always visible above input bar
  const quickPills = [
    { label: "Top savings ideas", query: "What are the top savings ideas?" },
    { label: "Top 3 highest cost services", query: "Which 3 services cost the most in this dataset?" },
    { label: "Idle resources savings", query: "How much can we save by fixing idle resources?" },
    { label: "Compute Engine spend", query: "How much did we spend on Compute Engine?" },
    { label: "Regional breakdown", query: "What are the top spending regions?" },
    { label: "Underused machines", query: "What can we save on underused machines?" },
  ];

  const handleSend = (text?: string) => {
    const q = text || input;
    if (!q.trim() || isStreaming) return;
    sendMessage(q.trim());
    setInput("");
    setShowFaqModal(false);
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col justify-between space-y-3 relative">
      {/* Top Header & Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-1 border-b border-slate-200">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Ask AI</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Ask questions about your cloud costs. All numbers are verified directly against your billing records
            {activeDataset?.name ? ` (${activeDataset.name})` : ""}.
          </p>
        </div>

        {/* Action Buttons: FAQ / Quick Questions and Clear Chat */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setShowFaqModal(true)}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition shadow-2xs"
          >
            <HelpCircle className="w-3.5 h-3.5 text-slate-500" />
            <span>Questions & FAQ</span>
          </button>

          <button
            type="button"
            onClick={clearChat}
            disabled={messages.length === 0 || isStreaming}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-white hover:bg-slate-50 hover:text-rose-600 border border-slate-200 rounded-lg transition disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs"
            title="Clear conversation history for this dataset"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Clear chat</span>
          </button>
        </div>
      </div>

      {/* Main Chat Scroll Area */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200/90 shadow-2xs p-5 overflow-y-auto space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto space-y-3 py-8">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 mb-1">
              <MessageSquare className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-800">What would you like to explore?</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              Query total spend, top services, idle resources, or savings recommendations directly from your data.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full pt-3">
              {quickPills.slice(0, 4).map((p) => (
                <button
                  key={p.label}
                  onClick={() => handleSend(p.query)}
                  className="p-3 text-left bg-slate-50/70 hover:bg-blue-50/50 hover:border-blue-200 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 transition"
                >
                  <div className="font-semibold text-slate-900">{p.label}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5 truncate">{p.query}</div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, idx) => (
            <div
              key={m.id || idx}
              className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed ${
                  m.role === "user"
                    ? "bg-slate-900 text-white rounded-tr-xs shadow-xs"
                    : "bg-slate-50/80 text-slate-900 border border-slate-200/90 rounded-tl-xs shadow-2xs"
                }`}
              >
                <div className="whitespace-pre-wrap">
                  {m.content ? (
                    m.content
                  ) : (
                    <span className="text-slate-400 italic flex items-center space-x-2">
                      <Sparkles className="w-3.5 h-3.5 animate-pulse text-blue-600" />
                      <span>Checking billing records with database queries...</span>
                    </span>
                  )}
                </div>

                {/* Verification badge & technical drawer */}
                {m.role === "assistant" && m.content && (
                  <div className="mt-3 pt-3 border-t border-slate-200/60 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    {/* Answer check badge */}
                    <div className="flex items-center space-x-1.5 text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>
                        {m.faithfulnessPassed ? "All numbers match your data" : "Some numbers could not be checked"}
                      </span>
                    </div>

                    {/* How was this worked out toggle */}
                    {(m.sqlQueries?.length || 0) > 0 && (
                      <button
                        onClick={() =>
                          setActiveDetailsIndex(activeDetailsIndex === idx ? null : idx)
                        }
                        className="text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center space-x-1 cursor-pointer"
                      >
                        <span>How was this worked out?</span>
                        <ChevronDown
                          className={`w-3 h-3 transition-transform ${
                            activeDetailsIndex === idx ? "rotate-180" : ""
                          }`}
                        />
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Technical details drawer */}
              {activeDetailsIndex === idx && m.sqlQueries && (
                <div className="mt-2 max-w-2xl w-full p-3 bg-slate-900 text-slate-200 rounded-lg text-[11px] font-mono space-y-2 border border-slate-800 shadow-md">
                  <div className="flex items-center justify-between text-slate-400 font-semibold text-[10px] uppercase tracking-wide">
                    <span>Database queries executed:</span>
                    <span className="text-slate-500">{m.sqlQueries.length} query</span>
                  </div>
                  {m.sqlQueries.map((sql, sIdx) => (
                    <pre
                      key={sIdx}
                      className="p-2.5 bg-slate-950 rounded text-emerald-400 overflow-x-auto border border-slate-800/80 leading-normal"
                    >
                      {sql}
                    </pre>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Always-Visible Quick Questions Pill Strip */}
      <div className="flex items-center space-x-2 overflow-x-auto py-1 px-1 scrollbar-thin">
        <span className="text-[11px] font-semibold text-slate-500 whitespace-nowrap">
          Quick queries:
        </span>
        {quickPills.map((pill) => (
          <button
            key={pill.label}
            type="button"
            onClick={() => handleSend(pill.query)}
            disabled={isStreaming}
            className="shrink-0 px-2.5 py-1 text-[11px] font-medium bg-white hover:bg-blue-50/70 hover:text-blue-700 hover:border-blue-200 border border-slate-200 rounded-lg text-slate-700 transition disabled:opacity-50 cursor-pointer shadow-2xs"
          >
            {pill.label}
          </button>
        ))}
      </div>

      {/* Input box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex items-center space-x-3 bg-white p-2 rounded-xl border border-slate-200/90 shadow-2xs focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your cloud costs..."
          disabled={isStreaming}
          className="flex-1 px-3 py-2 text-xs text-slate-800 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!input.trim() || isStreaming}
          className="p-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition disabled:opacity-40 cursor-pointer shadow-2xs"
          title="Send question"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>

      {/* Permanent FAQ & Suggested Prompts Modal */}
      {showFaqModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 bg-blue-50 text-blue-700 rounded-lg border border-blue-100">
                  <HelpCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Frequently Asked Questions</h3>
                  <p className="text-xs text-slate-500">
                    Click any question to immediately query your billing and usage data.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowFaqModal(false)}
                className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              {/* How Ask AI works banner */}
              <div className="p-3.5 bg-blue-50/70 border border-blue-100 rounded-xl flex items-start space-x-3 text-xs text-blue-950">
                <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <span className="font-semibold text-blue-900">How Ask AI Works (Zero Hallucination)</span>
                  <p className="text-blue-800/80 leading-relaxed text-[11px]">
                    Unlike generic text search (RAG) which guesses answers from text snippets, Ask AI uses <strong>database tool-calling</strong>. It translates your prompt into precise PostgreSQL queries, runs them against your real billing records, and automatically verifies that every single number quoted in the response matches the query output.
                  </p>
                </div>
              </div>

              {/* Categorized Question Lists */}
              {faqCategories.map((cat) => (
                <div key={cat.title} className="space-y-2">
                  <div className="flex items-center space-x-2 text-xs font-bold text-slate-800 uppercase tracking-wide">
                    {cat.icon}
                    <span>{cat.title}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-1.5">
                    {cat.questions.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => handleSend(q)}
                        disabled={isStreaming}
                        className="text-left px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white hover:bg-blue-50/60 hover:border-blue-200 text-xs text-slate-700 transition flex items-center justify-between group disabled:opacity-50"
                      >
                        <span className="font-medium group-hover:text-blue-900">{q}</span>
                        <Send className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex justify-end">
              <button
                type="button"
                onClick={() => setShowFaqModal(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

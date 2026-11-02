import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Lightbulb,
  DollarSign,
  MessageSquare,
  Database,
  ChevronDown,
  TrendingUp,
  Award,
  Clock,
  AlertTriangle,
  Cloud,
} from "lucide-react";
import { useDataset } from "../context/DatasetContext";

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { activeDatasetId, setActiveDatasetId, datasets, activeDataset, summary } = useDataset();
  const [moreOpen, setMoreOpen] = useState(false);

  const mainNav = [
    { label: "Overview", path: "/", icon: LayoutDashboard },
    { label: "Savings ideas", path: "/recommendations", icon: Lightbulb },
    { label: "Costs", path: "/explorer", icon: DollarSign },
    { label: "Ask AI", path: "/copilot", icon: MessageSquare },
    { label: "Data", path: "/data", icon: Database },
  ];

  const moreNav = [
    { label: "Cost jumps", path: "/anomalies", icon: TrendingUp },
    { label: "Scores", path: "/eval", icon: Award },
    { label: "Activity log", path: "/audit", icon: Clock },
  ];

  const isMoreActive = moreNav.some((item) => location.pathname === item.path);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-800">
      {/* Slim notice for CSV dataset */}
      {activeDataset?.kind === "csv" && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-900 text-center font-medium">
          Real-format GCP billing sample, for demo only.
        </div>
      )}

      {/* Top Header */}
      <header className="bg-white border-b border-slate-200/90 h-16 flex items-center justify-between px-6 sticky top-0 z-30 shadow-2xs">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-xs">
            <Cloud className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold text-slate-900 leading-none tracking-tight">CloudCost Copilot</h1>
              <span className="text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                FinOps
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Cloud spend intelligence & waste optimization</p>
          </div>
        </div>

        {/* Dataset Switcher & Warnings */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <label htmlFor="dataset-select" className="text-xs font-semibold text-slate-600">
              Dataset:
            </label>
            <select
              id="dataset-select"
              value={activeDatasetId || ""}
              onChange={(e) => setActiveDatasetId(e.target.value)}
              className="text-xs bg-white border border-slate-300 rounded-lg px-3 py-1.5 font-medium text-slate-800 hover:border-slate-400 transition shadow-2xs focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} {d.kind === "csv" ? "(Sample file)" : "(Full history)"}
                </option>
              ))}
            </select>
          </div>

          {/* Warnings Badge if any */}
          {summary && summary.kind === "csv" && (
            <Link
              to="/data"
              className="inline-flex items-center text-xs text-slate-600 hover:text-slate-900 bg-slate-50 hover:bg-slate-100 border border-slate-200 px-2.5 py-1.5 rounded-lg transition"
              title="View data notes"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mr-1.5" />
              <span className="font-medium">Data notes</span>
            </Link>
          )}
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 flex">
        {/* Left Sidebar */}
        <aside className="w-60 bg-white border-r border-slate-200/90 p-4 flex flex-col justify-between shrink-0">
          <nav className="space-y-1">
            {mainNav.map((item) => {
              const Icon = item.icon;
              const active = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition ${
                    active
                      ? "bg-blue-50 text-blue-700 font-semibold shadow-2xs border border-blue-100"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <Icon className={`w-4 h-4 mr-3 ${active ? "text-blue-600" : "text-slate-400"}`} />
                  {item.label}
                </Link>
              );
            })}

            {/* More Menu Dropdown */}
            <div className="relative pt-2">
              <button
                onClick={() => setMoreOpen(!moreOpen)}
                className={`w-full flex items-center justify-between px-3 py-2.5 text-sm font-medium rounded-lg transition ${
                  isMoreActive
                    ? "bg-slate-100 text-slate-900 font-semibold"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <span className="flex items-center">
                  <span className="w-4 h-4 mr-3 text-slate-400 font-bold">•</span>
                  More tools
                </span>
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${moreOpen ? "rotate-180" : ""}`} />
              </button>

              {moreOpen && (
                <div className="pl-4 mt-1 space-y-1 border-l-2 border-slate-100 ml-5">
                  {moreNav.map((item) => {
                    const Icon = item.icon;
                    const active = location.pathname === item.path;
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => setMoreOpen(false)}
                        className={`flex items-center px-3 py-2 text-xs font-medium rounded-md transition ${
                          active
                            ? "bg-blue-50 text-blue-700 font-semibold"
                            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`}
                      >
                        <Icon className={`w-3.5 h-3.5 mr-2.5 ${active ? "text-blue-600" : "text-slate-400"}`} />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>

          <div className="text-[11px] text-slate-400 px-3 py-2 border-t border-slate-100 flex items-center justify-between">
            <span>CloudCost Copilot</span>
            <span className="font-mono text-[10px] text-slate-400">v1.0</span>
          </div>
        </aside>

        {/* Content Area */}
        <main className="flex-1 p-8 max-w-6xl mx-auto overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};


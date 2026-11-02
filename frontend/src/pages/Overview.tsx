import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  DollarSign,
  TrendingDown,
  AlertCircle,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
} from "recharts";
import { useDataset } from "../context/DatasetContext";
import { api } from "../api/client";
import {
  formatMoney,
  translateFindingType,
  translateConfidence,
  translateUnit,
  translateBasis,
} from "../utils/formatters";

export const Overview: React.FC = () => {
  const { activeDatasetId, summary, isLoadingSummary, activeDataset } = useDataset();

  // Daily spend for chart 1
  const { data: dailyCosts = [] } = useQuery({
    queryKey: ["costs", activeDatasetId, "day"],
    queryFn: () => (activeDatasetId ? api.getCosts({ dataset_id: activeDatasetId, group_by: "day", limit: 30 }) : []),
    enabled: !!activeDatasetId,
  });

  // Top services for chart 2
  const { data: topServices = [] } = useQuery({
    queryKey: ["topCosts", activeDatasetId],
    queryFn: () => (activeDatasetId ? api.getTopCosts(activeDatasetId, 5) : []),
    enabled: !!activeDatasetId,
  });

  // Top 5 savings ideas
  const { data: recommendations = [], refetch: refetchRecs } = useQuery({
    queryKey: ["recommendations", activeDatasetId, "open"],
    queryFn: () => (activeDatasetId ? api.getRecommendations({ dataset_id: activeDatasetId, status: "open", sort: "priority" }) : []),
    enabled: !!activeDatasetId,
  });

  const topIdeas = recommendations.slice(0, 5);

  const handleGenerateIdeas = async () => {
    if (!activeDatasetId) return;
    await api.runDetectors(activeDatasetId);
    refetchRecs();
  };

  if (isLoadingSummary) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-slate-200 rounded w-48 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-28 bg-slate-200 rounded-xl animate-pulse" />
          <div className="h-28 bg-slate-200 rounded-xl animate-pulse" />
          <div className="h-28 bg-slate-200 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Overview</h2>
        <p className="text-sm text-slate-500 mt-1">A simple view of your cloud costs and potential savings.</p>
      </div>

      {/* 3 Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Cost */}
        <div className="card-surface rounded-xl p-5 border border-slate-200/90 shadow-2xs flex items-center space-x-4">
          <div className="p-3 bg-blue-50 text-blue-700 rounded-xl border border-blue-100">
            <DollarSign className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Cloud Spend</p>
            <p className="text-2xl font-bold text-slate-900 tracking-tight tabular-nums mt-0.5">{formatMoney(summary?.total_cost)}</p>
            <p className="text-xs text-slate-400 mt-0.5">
              {summary?.resources || 0} active resources counted
            </p>
          </div>
        </div>

        {/* Possible Savings */}
        <div className="card-surface rounded-xl p-5 border border-slate-200/90 shadow-2xs flex items-center space-x-4">
          <div className="p-3 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100">
            <TrendingDown className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Identified Savings</p>
            <p className="text-2xl font-bold text-emerald-600 tracking-tight tabular-nums mt-0.5">
              {summary?.savings_range?.high
                ? `${formatMoney(summary.savings_range.low)} - ${formatMoney(summary.savings_range.high)}`
                : "$0"}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              {activeDataset?.kind === "csv" ? "in this billing cycle" : "estimated per month"}
            </p>
          </div>
        </div>

        {/* Items to Review */}
        <div className="card-surface rounded-xl p-5 border border-slate-200/90 shadow-2xs flex items-center space-x-4">
          <div className="p-3 bg-amber-50 text-amber-700 rounded-xl border border-amber-100">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Optimization Items</p>
            <p className="text-2xl font-bold text-slate-900 tracking-tight tabular-nums mt-0.5">{summary?.findings_count || 0}</p>
            <p className="text-xs text-slate-400 mt-0.5">
              {summary?.anomalies_count ? `${summary.anomalies_count} spend spikes detected` : "Ready for review"}
            </p>
          </div>
        </div>
      </div>

      {/* 2 Charts Only */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Daily Spend Line */}
        <div className="card-surface p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Cost trend over time</h3>
            {summary?.is_derived_daily && (
              <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                derived daily
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500">Daily spending across all services.</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dailyCosts} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="key" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  formatter={(val: any) => [`$${val}`, "Cost"]}
                  labelFormatter={(lbl) => `Date: ${lbl}`}
                  contentStyle={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}
                />
                <Line type="monotone" dataKey="billed_cost" stroke="#2563eb" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Top Services Bar */}
        <div className="card-surface p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Top spending services</h3>
          </div>
          <p className="text-xs text-slate-500">The 5 services using the largest share of your budget.</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topServices} layout="vertical" margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={(v) => `$${v}`} />
                <YAxis dataKey="service_name" type="category" tick={{ fontSize: 10, fill: "#64748b" }} width={110} />
                <Tooltip
                  formatter={(val: any) => [`$${val}`, "Cost"]}
                  contentStyle={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}
                />
                <Bar dataKey="billed_cost" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Top 5 Savings Ideas */}
      <div className="card-surface rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
        <div className="p-5 border-b border-slate-200/90 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Top savings opportunities</h3>
            <p className="text-xs text-slate-500 mt-0.5">High-impact actions to eliminate idle and oversized resources.</p>
          </div>
          {recommendations.length === 0 ? (
            <button
              onClick={handleGenerateIdeas}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition shadow-2xs"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Scan for savings</span>
            </button>
          ) : (
            <Link
              to="/recommendations"
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 inline-flex items-center space-x-1"
            >
              <span>View all {recommendations.length}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>

        {recommendations.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">
            No savings ideas found yet. Click &quot;Scan for savings&quot; to inspect your resources.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {topIdeas.map((rec) => {
              const conf = translateConfidence(rec.confidence);
              return (
                <div key={rec.id} className="p-4 flex items-center justify-between hover:bg-slate-50/80 transition">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-slate-900 font-mono">{rec.resource_id}</span>
                      <span className="text-xs text-slate-500">• {rec.service_name}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-blue-700 font-semibold bg-blue-50 border border-blue-200/60 px-2 py-0.5 rounded-md">
                        {translateFindingType(rec.type)}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-md border font-medium ${conf.color}`}>
                        {conf.label} surety
                      </span>
                    </div>
                  </div>

                  <div className="text-right">
                    <p className="text-sm font-bold text-slate-900 tabular-nums">
                      {formatMoney(rec.savings_mid)}{" "}
                      <span className="text-xs font-normal text-slate-500">
                        {translateUnit(rec.savings_unit)}
                      </span>
                    </p>
                    <p className="text-xs text-slate-400">
                      {translateBasis(rec.savings_basis)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};


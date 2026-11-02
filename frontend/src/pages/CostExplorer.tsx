import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { BarChart3, TrendingUp, Sparkles } from "lucide-react";
import { useDataset } from "../context/DatasetContext";
import { api } from "../api/client";
import { formatMoney, formatPercent } from "../utils/formatters";

export const CostExplorer: React.FC = () => {
  const { activeDatasetId } = useDataset();

  const [viewMode, setViewMode] = useState<"historical" | "forecast">("historical");
  const [groupBy, setGroupBy] = useState<"service" | "region" | "day">("service");
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");

  const { data: costs = [], isLoading } = useQuery({
    queryKey: ["costs", activeDatasetId, groupBy, fromDate, toDate],
    queryFn: () => {
      if (!activeDatasetId) return [];
      return api.getCosts({
        dataset_id: activeDatasetId,
        group_by: groupBy,
        from: fromDate || undefined,
        to: toDate || undefined,
        limit: 50,
      });
    },
    enabled: !!activeDatasetId,
  });

  const { data: forecastData, isLoading: isLoadingForecast } = useQuery({
    queryKey: ["costForecast", activeDatasetId],
    queryFn: () => (activeDatasetId ? api.getCostForecast(activeDatasetId, 30) : null),
    enabled: !!activeDatasetId && viewMode === "forecast",
  });

  return (
    <div className="space-y-6">
      {/* Title & View Mode Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Costs &amp; Projections</h2>
          <p className="text-sm text-slate-500 mt-1">
            Analyze historical cloud expenditure or forecast next month&apos;s run-rate with seasonal ML models.
          </p>
        </div>

        {/* View Switcher: Historical vs Forecast */}
        <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 shadow-2xs">
          <button
            type="button"
            onClick={() => setViewMode("historical")}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === "historical"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Historical Spend</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode("forecast")}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === "forecast"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>30-Day Forecast</span>
          </button>
        </div>
      </div>

      {viewMode === "historical" ? (
        <>
          {/* Filter Controls (No more than 3 visible) */}
          <div className="card-surface p-4 rounded-xl border border-slate-200/90 shadow-2xs flex flex-wrap items-center gap-4 text-xs">
            {/* 1. Group By */}
            <div className="flex items-center space-x-2">
              <label htmlFor="group-by-select" className="font-semibold text-slate-600">Group by:</label>
              <select
                id="group-by-select"
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value as any)}
                className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="service">Service</option>
                <option value="region">Region</option>
                <option value="day">Day</option>
              </select>
            </div>

            {/* 2. Start Date */}
            <div className="flex items-center space-x-2">
              <label htmlFor="from-date-input" className="font-semibold text-slate-600">From:</label>
              <input
                id="from-date-input"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            {/* 3. End Date */}
            <div className="flex items-center space-x-2">
              <label htmlFor="to-date-input" className="font-semibold text-slate-600">To:</label>
              <input
                id="to-date-input"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>

          {/* 1 Chart */}
          <div className="card-surface p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
            <h3 className="text-sm font-semibold text-slate-900 capitalize">
              Cost Breakdown by {groupBy}
            </h3>
            <div className="h-64">
              {isLoading ? (
                <div className="h-full bg-slate-50 rounded-lg animate-pulse" />
              ) : costs.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-slate-400">
                  No cost entries found for the selected filter.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={costs.slice(0, 15)} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
                    <XAxis
                      dataKey="key"
                      tick={{ fontSize: 10, fill: "#64748b" }}
                      interval={0}
                      angle={-25}
                      textAnchor="end"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#64748b" }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      formatter={(val: any) => [`$${val}`, "Cost"]}
                      contentStyle={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}
                    />
                    <Bar dataKey="billed_cost" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* 1 Table */}
          <div className="card-surface rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
            <div className="p-4 border-b border-slate-200/90 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">Summary Breakdown</h3>
              <span className="text-xs text-slate-500 font-mono">{costs.length} items</span>
            </div>

            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200/90 text-slate-600 font-semibold">
                  <th className="py-3 px-4 capitalize">{groupBy}</th>
                  <th className="py-3 px-4 text-right">Total Cost</th>
                  <th className="py-3 px-4 text-right">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {costs.map((row) => (
                  <tr key={row.key} className="hover:bg-slate-50/80">
                    <td className="py-2.5 px-4 font-semibold text-slate-800">{row.key}</td>
                    <td className="py-2.5 px-4 text-right font-bold text-slate-900 tabular-nums">
                      {formatMoney(row.billed_cost)}
                    </td>
                    <td className="py-2.5 px-4 text-right text-slate-600 font-mono tabular-nums">
                      {formatPercent(row.share_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        /* Forecast Mode */
        <div className="space-y-6">
          {/* Forecast KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card-surface p-4 rounded-xl border border-slate-200/90 shadow-2xs">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Projected Next 30 Days
              </span>
              <div className="flex items-baseline space-x-2 mt-1">
                <span className="text-2xl font-bold text-slate-900 tabular-nums">
                  {formatMoney(forecastData?.projected_next_month_spend)}
                </span>
                {forecastData && (
                  <span
                    className={`text-xs font-semibold ${
                      forecastData.projected_growth_pct > 0 ? "text-amber-600" : "text-emerald-600"
                    }`}
                  >
                    {forecastData.projected_growth_pct > 0 ? "+" : ""}
                    {forecastData.projected_growth_pct}%
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                vs previous 30-day run rate ({formatMoney(forecastData?.current_run_rate_monthly)})
              </p>
            </div>

            <div className="card-surface p-4 rounded-xl border border-slate-200/90 shadow-2xs">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                95% Confidence Interval
              </span>
              <div className="text-lg font-bold text-slate-800 tabular-nums mt-1.5">
                {formatMoney(forecastData?.lower_bound_monthly)} – {formatMoney(forecastData?.upper_bound_monthly)}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Optimistic vs pessimistic budget range
              </p>
            </div>

            <div className="card-surface p-4 rounded-xl border border-slate-200/90 shadow-2xs">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Forecasting Model
              </span>
              <div className="flex items-center space-x-1.5 text-sm font-bold text-blue-700 mt-1.5">
                <Sparkles className="w-4 h-4 text-blue-600" />
                <span>Holt-Winters Additive</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                7-day seasonal cycle + baseline trend dampening
              </p>
            </div>
          </div>

          {/* Forecast Trend Chart */}
          <div className="card-surface p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">30-Day Daily Spend Projection</h3>
                <p className="text-xs text-slate-500">
                  Daily projected expenditure with upper and lower variance bounds.
                </p>
              </div>
              <div className="flex items-center space-x-4 text-xs font-medium">
                <span className="flex items-center space-x-1 text-blue-600">
                  <span className="w-3 h-0.5 bg-blue-600 rounded"></span>
                  <span>Expected</span>
                </span>
                <span className="flex items-center space-x-1 text-slate-400">
                  <span className="w-3 h-0.5 bg-slate-300 rounded"></span>
                  <span>Bounds (95% CI)</span>
                </span>
              </div>
            </div>

            <div className="h-64">
              {isLoadingForecast ? (
                <div className="h-full bg-slate-50 rounded-lg animate-pulse" />
              ) : !forecastData?.daily_forecast?.length ? (
                <div className="h-full flex items-center justify-center text-xs text-slate-400">
                  Insufficient historical records to build 30-day forecast.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastData.daily_forecast} margin={{ top: 10, right: 10, left: 10, bottom: 25 }}>
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "#64748b" }}
                      interval={3}
                      angle={-25}
                      textAnchor="end"
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#64748b" }}
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      formatter={(val: any, name: any) => [`$${val}`, name === "expected" ? "Expected" : name === "upper" ? "Upper Bound" : "Lower Bound"]}
                      labelFormatter={(lbl) => `Projected: ${lbl}`}
                      contentStyle={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.05)" }}
                    />
                    <Line type="monotone" dataKey="upper" stroke="#cbd5e1" strokeDasharray="3 3" dot={false} strokeWidth={1.5} />
                    <Line type="monotone" dataKey="expected" stroke="#2563eb" strokeWidth={2.5} dot={false} />
                    <Line type="monotone" dataKey="lower" stroke="#cbd5e1" strokeDasharray="3 3" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


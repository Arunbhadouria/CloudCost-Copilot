import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { useDataset } from "../context/DatasetContext";
import { api } from "../api/client";
import { formatMoney, formatPercent } from "../utils/formatters";

export const CostExplorer: React.FC = () => {
  const { activeDatasetId } = useDataset();

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

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Costs</h2>
        <p className="text-sm text-slate-500 mt-1">
          Explore where your cloud spend goes by service, region, or day.
        </p>
      </div>

      {/* Filter Controls (No more than 3 visible) */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center gap-4 text-xs">
        {/* 1. Group By */}
        <div className="flex items-center space-x-2">
          <label htmlFor="group-by-select" className="font-medium text-slate-600">Group by:</label>
          <select
            id="group-by-select"
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as any)}
            className="bg-slate-50 border border-slate-300 rounded-md px-3 py-1.5 text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="service">Service</option>
            <option value="region">Region</option>
            <option value="day">Day</option>
          </select>
        </div>

        {/* 2. Start Date */}
        <div className="flex items-center space-x-2">
          <label htmlFor="from-date-input" className="font-medium text-slate-600">From:</label>
          <input
            id="from-date-input"
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="bg-slate-50 border border-slate-300 rounded-md px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* 3. End Date */}
        <div className="flex items-center space-x-2">
          <label htmlFor="to-date-input" className="font-medium text-slate-600">To:</label>
          <input
            id="to-date-input"
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="bg-slate-50 border border-slate-300 rounded-md px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {/* 1 Chart */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-3">
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
                  tick={{ fontSize: 10 }}
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                />
                <YAxis
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => `$${v}`}
                />
                <Tooltip
                  formatter={(val: any) => [`$${val}`, "Cost"]}
                  contentStyle={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0" }}
                />
                <Bar dataKey="billed_cost" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 1 Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Summary Table</h3>
          <span className="text-xs text-slate-400">{costs.length} items</span>
        </div>

        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
              <th className="py-3 px-4 capitalize">{groupBy}</th>
              <th className="py-3 px-4 text-right">Total Cost</th>
              <th className="py-3 px-4 text-right">Share</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {costs.map((row) => (
              <tr key={row.key} className="hover:bg-slate-50">
                <td className="py-2.5 px-4 font-medium text-slate-800">{row.key}</td>
                <td className="py-2.5 px-4 text-right font-semibold text-slate-900">
                  {formatMoney(row.billed_cost)}
                </td>
                <td className="py-2.5 px-4 text-right text-slate-500 font-mono">
                  {formatPercent(row.share_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};


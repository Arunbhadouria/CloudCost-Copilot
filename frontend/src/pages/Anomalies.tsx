import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, AlertTriangle, Cpu } from "lucide-react";
import { useDataset } from "../context/DatasetContext";
import { api, type AnomalyItem } from "../api/client";
import { formatMoney, formatDate } from "../utils/formatters";

export const Anomalies: React.FC = () => {
  const { activeDatasetId, activeDataset } = useDataset();
  const [filterType, setFilterType] = useState<"all" | "stl" | "iforest">("all");

  const { data: anomalies = [], isLoading } = useQuery({
    queryKey: ["anomalies", activeDatasetId],
    queryFn: () => (activeDatasetId ? api.getAnomalies(activeDatasetId) : []),
    enabled: !!activeDatasetId,
  });

  const getMethod = (anom: AnomalyItem): "stl" | "iforest" => {
    if (Array.isArray(anom.explained_by) && anom.explained_by.length > 0) {
      if (anom.explained_by[0]?.method === "isolation_forest") return "iforest";
    }
    return "stl";
  };

  const filteredAnomalies = anomalies.filter((a) => {
    if (filterType === "all") return true;
    return getMethod(a) === filterType;
  });

  return (
    <div className="space-y-6">
      {/* Title & Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Cost &amp; Usage Anomalies</h2>
          <p className="text-sm text-slate-500 mt-1">
            Detects unseasonal spending spikes (STL decomposition) and multidimensional resource outliers (Isolation Forest).
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 bg-slate-100 p-1 rounded-xl border border-slate-200 shadow-2xs">
          <button
            type="button"
            onClick={() => setFilterType("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              filterType === "all"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            All ({anomalies.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterType("stl")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              filterType === "stl"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Cost Spikes (STL)
          </button>
          <button
            type="button"
            onClick={() => setFilterType("iforest")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              filterType === "iforest"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Resource Outliers (Isolation Forest)
          </button>
        </div>
      </div>

      {activeDataset?.kind === "csv" ? (
        <div className="card-surface p-8 rounded-xl border border-slate-200/90 shadow-2xs text-center space-y-2">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-800">Insufficient history</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            This sample dataset covers only about two months of data. Reliable detection of unusual cost jumps requires at least 56 days of daily records.
          </p>
        </div>
      ) : isLoading ? (
        <div className="p-8 space-y-3">
          <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
          <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
        </div>
      ) : filteredAnomalies.length === 0 ? (
        <div className="card-surface p-8 rounded-xl border border-slate-200/90 shadow-2xs text-center text-xs text-slate-500">
          No anomalies detected for the selected filter.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAnomalies.map((anom) => {
            const method = getMethod(anom);
            const detail =
              Array.isArray(anom.explained_by) && anom.explained_by.length > 0
                ? (anom.explained_by[0] as Record<string, any>)
                : null;
            return (
              <div
                key={anom.id}
                className="card-surface p-4 rounded-xl border border-slate-200/90 shadow-2xs flex flex-wrap items-center justify-between gap-3"
              >
                <div className="space-y-1 max-w-xl">
                  <div className="flex items-center space-x-2">
                    {method === "iforest" ? (
                      <Cpu className="w-4 h-4 text-purple-600" />
                    ) : (
                      <TrendingUp className="w-4 h-4 text-rose-500" />
                    )}
                    <span className="text-xs font-bold text-slate-900">{anom.service_name}</span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {formatDate(anom.start_date)} - {formatDate(anom.end_date)}
                    </span>
                    {method === "iforest" ? (
                      <span className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-purple-50 text-purple-700 border border-purple-200">
                        Isolation Forest
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                        STL Seasonal
                      </span>
                    )}
                  </div>

                  {detail?.reason && (
                    <p className="text-[11px] text-slate-600 pl-6">
                      {detail.reason}
                    </p>
                  )}

                  <div className="flex items-center space-x-3 text-xs text-slate-600 pl-6">
                    <span>Observed: <strong className="font-mono tabular-nums">{formatMoney(anom.actual)}</strong></span>
                    <span>Expected Baseline: <strong className="font-mono tabular-nums">{formatMoney(anom.expected)}</strong></span>
                  </div>
                </div>

                <div className="text-right">
                  <span
                    className={`px-2.5 py-1 text-[11px] font-semibold rounded-md uppercase tracking-wider ${
                      anom.severity === "high"
                        ? "bg-rose-50 text-rose-700 border border-rose-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    {anom.severity} anomaly
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};


import React from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, AlertTriangle } from "lucide-react";
import { useDataset } from "../context/DatasetContext";
import { api } from "../api/client";
import { formatMoney, formatDate } from "../utils/formatters";

export const Anomalies: React.FC = () => {
  const { activeDatasetId, activeDataset } = useDataset();

  const { data: anomalies = [], isLoading } = useQuery({
    queryKey: ["anomalies", activeDatasetId],
    queryFn: () => (activeDatasetId ? api.getAnomalies(activeDatasetId) : []),
    enabled: !!activeDatasetId,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Cost jumps</h2>
        <p className="text-sm text-slate-500 mt-1">
          Unusual cost increases that deviate from regular weekly spending patterns.
        </p>
      </div>

      {activeDataset?.kind === "csv" ? (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-xs text-center space-y-2">
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
      ) : anomalies.length === 0 ? (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-xs text-center text-xs text-slate-500">
          No unusual cost jumps detected for this dataset.
        </div>
      ) : (
        <div className="space-y-3">
          {anomalies.map((anom) => (
            <div
              key={anom.id}
              className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <TrendingUp className="w-4 h-4 text-red-500" />
                  <span className="text-xs font-bold text-slate-900">{anom.service_name}</span>
                  <span className="text-[11px] text-slate-400">
                    {formatDate(anom.start_date)} - {formatDate(anom.end_date)}
                  </span>
                </div>
                <div className="flex items-center space-x-3 text-xs text-slate-600">
                  <span>Actual: <strong>{formatMoney(anom.actual)}</strong></span>
                  <span>Expected: <strong>{formatMoney(anom.expected)}</strong></span>
                </div>
              </div>

              <div className="text-right">
                <span className="px-2.5 py-1 text-[11px] font-semibold rounded-md uppercase tracking-wider bg-red-50 text-red-700 border border-red-200">
                  {anom.severity} jump
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};


import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X,
  Check,
  Ban,
  Sparkles,
  Terminal,
  Copy,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { useDataset } from "../context/DatasetContext";
import { api, type RecommendationItem, type DryRunResponse } from "../api/client";
import {
  formatMoney,
  translateFindingType,
  translateConfidence,
  translateEffort,
  translateBasis,
  translateUnit,
} from "../utils/formatters";

export const Recommendations: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeDatasetId } = useDataset();

  const [statusFilter, setStatusFilter] = useState<string>("open");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [selectedRec, setSelectedRec] = useState<RecommendationItem | null>(null);
  const [previewResult, setPreviewResult] = useState<DryRunResponse | null>(null);
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // Fetch recommendations
  const { data: recommendations = [], isLoading, refetch } = useQuery({
    queryKey: ["recommendations", activeDatasetId, statusFilter, typeFilter],
    queryFn: () => {
      if (!activeDatasetId) return [];
      return api.getRecommendations({
        dataset_id: activeDatasetId,
        status: statusFilter === "all" ? undefined : statusFilter,
        type: typeFilter === "all" ? undefined : typeFilter,
        sort: "priority",
      });
    },
    enabled: !!activeDatasetId,
  });

  // Action mutations
  const acceptMutation = useMutation({
    mutationFn: (id: number) => api.acceptRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      queryClient.invalidateQueries({ queryKey: ["datasetSummary"] });
      if (selectedRec) setSelectedRec({ ...selectedRec, status: "accepted" });
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (id: number) => api.dismissRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      queryClient.invalidateQueries({ queryKey: ["datasetSummary"] });
      if (selectedRec) setSelectedRec({ ...selectedRec, status: "dismissed" });
    },
  });

  const previewMutation = useMutation({
    mutationFn: (id: number) => api.previewFix(id),
    onSuccess: (data) => {
      setPreviewResult(data);
    },
  });

  const handleOpenDrawer = (rec: RecommendationItem) => {
    setSelectedRec(rec);
    setPreviewResult(null);
  };

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(label);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const handleRunFinders = async () => {
    if (!activeDatasetId) return;
    await api.runDetectors(activeDatasetId);
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Title & Action */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Savings ideas</h2>
          <p className="text-sm text-slate-500 mt-1">
            Recommended changes to lower your cloud spending without hurting performance.
          </p>
        </div>
        <button
          onClick={handleRunFinders}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-2xs transition"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Refresh ideas</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/90 pb-3">
        {/* Status Tabs */}
        <div className="flex items-center space-x-1.5">
          {["open", "accepted", "dismissed", "all"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize transition ${
                statusFilter === st
                  ? "bg-blue-50 text-blue-700 font-semibold border border-blue-200/80 shadow-2xs"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Type Filter */}
        <div className="flex items-center space-x-2">
          <label htmlFor="type-filter-select" className="text-xs font-medium text-slate-500">Filter type:</label>
          <select
            id="type-filter-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600"
          >
            <option value="all">All types</option>
            <option value="idle">Not being used</option>
            <option value="underused">Bigger than needed</option>
            <option value="weak_signal">Needs a closer look</option>
          </select>
        </div>
      </div>

      {/* 5-Column Table */}
      <div className="card-surface rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
        {isLoading ? (
          <div className="p-8 space-y-4">
            <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
            <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
            <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
          </div>
        ) : recommendations.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm space-y-2">
            <p className="font-semibold text-slate-700">No savings ideas found in this view.</p>
            <p className="text-xs text-slate-400">
              Try switching status filters or click &quot;Refresh ideas&quot;.
            </p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200/90 text-xs font-semibold text-slate-600">
                <th className="py-3 px-4">Resource</th>
                <th className="py-3 px-4">What&apos;s wrong</th>
                <th className="py-3 px-4">Possible savings</th>
                <th className="py-3 px-4">How sure we are</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {recommendations.map((rec) => {
                const conf = translateConfidence(rec.confidence);
                return (
                  <tr
                    key={rec.id}
                    onClick={() => handleOpenDrawer(rec)}
                    className="hover:bg-slate-50/80 cursor-pointer transition"
                  >
                    {/* 1. Resource */}
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      <div className="font-mono text-xs">{rec.resource_id}</div>
                      <div className="text-[11px] font-normal text-slate-400">{rec.service_name}</div>
                    </td>

                    {/* 2. What's wrong */}
                    <td className="py-3 px-4">
                      <span className="inline-block px-2 py-0.5 rounded-md bg-blue-50 border border-blue-200/60 text-blue-700 font-semibold text-[11px]">
                        {translateFindingType(rec.type)}
                      </span>
                    </td>

                    {/* 3. Possible savings */}
                    <td className="py-3 px-4 font-bold text-slate-900 tabular-nums">
                      {formatMoney(rec.savings_mid)}{" "}
                      <span className="text-[11px] text-slate-400 font-normal">
                        {translateUnit(rec.savings_unit)}
                      </span>
                    </td>

                    {/* 4. How sure we are */}
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 rounded border text-[11px] font-medium ${conf.color}`}>
                        {conf.label}
                      </span>
                    </td>

                    {/* 5. Status */}
                    <td className="py-3 px-4 capitalize">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
                          rec.status === "accepted"
                            ? "bg-emerald-50 text-emerald-700"
                            : rec.status === "dismissed"
                            ? "bg-slate-100 text-slate-500"
                            : "bg-blue-50 text-blue-700"
                        }`}
                      >
                        {rec.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Slide-over Detail Drawer */}
      {selectedRec && (
        <div className="fixed inset-0 z-50 overflow-hidden flex justify-end bg-slate-900/30 backdrop-blur-xs transition">
          <div className="w-full max-w-lg bg-white h-full shadow-2xl p-6 flex flex-col justify-between overflow-y-auto">
            {/* Drawer Header */}
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">Savings Idea Details</h3>
                  <p className="text-xs text-slate-400">{selectedRec.resource_id}</p>
                </div>
                <button
                  onClick={() => setSelectedRec(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* What's wrong & explanation */}
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Finding
                  </span>
                  <span className="px-2 py-0.5 bg-blue-50 border border-blue-200/60 text-blue-700 rounded-md text-xs font-semibold">
                    {translateFindingType(selectedRec.type)}
                  </span>
                </div>
                <p className="text-xs text-slate-700 leading-relaxed bg-slate-50/80 p-3 rounded-xl border border-slate-200/80">
                  {selectedRec.reason}
                </p>
              </div>

              {/* Metrics grid */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/80">
                  <p className="text-[11px] font-medium text-slate-500">Service &amp; Region</p>
                  <p className="text-xs font-semibold text-slate-800 mt-0.5">{selectedRec.service_name}</p>
                </div>

                <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/80">
                  <p className="text-[11px] font-medium text-slate-500">How hard to fix</p>
                  <p className={`text-xs font-semibold mt-0.5 ${translateEffort(selectedRec.effort).color}`}>
                    {translateEffort(selectedRec.effort).label}
                  </p>
                </div>

                <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/80">
                  <p className="text-[11px] font-medium text-slate-500">Estimated savings</p>
                  <p className="text-xs font-bold text-slate-900 mt-0.5 tabular-nums">
                    {formatMoney(selectedRec.savings_mid)}{" "}
                    <span className="text-[10px] font-normal text-slate-500">
                      {translateUnit(selectedRec.savings_unit)}
                    </span>
                  </p>
                </div>

                <div className="bg-slate-50/80 p-3 rounded-xl border border-slate-200/80">
                  <p className="text-[11px] font-medium text-slate-500">Price calculation</p>
                  <p className="text-xs font-medium text-slate-700 mt-0.5">
                    {translateBasis(selectedRec.savings_basis)}
                  </p>
                </div>
              </div>

              {/* Preview Fix Section */}
              <div className="space-y-3 pt-2">
                <button
                  onClick={() => previewMutation.mutate(selectedRec.id)}
                  disabled={previewMutation.isPending}
                  className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-xl shadow-2xs transition"
                >
                  <Terminal className="w-4 h-4" />
                  <span>{previewMutation.isPending ? "Generating preview..." : "Preview the fix"}</span>
                </button>

                {previewResult && (
                  <div className="space-y-3 bg-slate-900 text-slate-100 p-4 rounded-xl text-xs font-mono">
                    {previewResult.is_prod || previewResult.status === "refused" || previewResult.manual_review ? (
                      <div className="flex items-center space-x-2 text-amber-400">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>{previewResult.warning || "Production resource: manual review required, no automated script generated."}</span>
                      </div>
                    ) : (
                      <>
                        {(previewResult.cli_command || previewResult.command) && (
                          <div>
                            <div className="flex items-center justify-between text-slate-400 mb-1">
                              <span className="text-[10px] uppercase">Command to apply fix</span>
                              <button
                                onClick={() => handleCopy((previewResult.cli_command || previewResult.command)!, "cmd")}
                                className="hover:text-white flex items-center space-x-1"
                              >
                                {copiedCmd === "cmd" ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                <span className="text-[10px]">Copy</span>
                              </button>
                            </div>
                            <pre className="p-2 bg-slate-950 rounded text-emerald-400 overflow-x-auto text-[11px]">
                              {previewResult.cli_command || previewResult.command}
                            </pre>
                          </div>
                        )}

                        {(previewResult.rollback_command || previewResult.rollback) && (
                          <div>
                            <div className="flex items-center justify-between text-slate-400 mb-1">
                              <span className="text-[10px] uppercase">How to undo it</span>
                              <button
                                onClick={() => handleCopy((previewResult.rollback_command || previewResult.rollback)!, "roll")}
                                className="hover:text-white flex items-center space-x-1"
                              >
                                {copiedCmd === "roll" ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                <span className="text-[10px]">Copy</span>
                              </button>
                            </div>
                            <pre className="p-2 bg-slate-950 rounded text-slate-300 overflow-x-auto text-[11px]">
                              {previewResult.rollback_command || previewResult.rollback}
                            </pre>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Actions */}
            <div className="border-t border-slate-100 pt-4 flex items-center space-x-3">
              <button
                onClick={() => acceptMutation.mutate(selectedRec.id)}
                disabled={selectedRec.status === "accepted"}
                className="flex-1 flex items-center justify-center space-x-1.5 py-2 px-3 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-lg transition disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                <span>Accept idea</span>
              </button>

              <button
                onClick={() => dismissMutation.mutate(selectedRec.id)}
                disabled={selectedRec.status === "dismissed"}
                className="flex-1 flex items-center justify-center space-x-1.5 py-2 px-3 border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium rounded-lg transition disabled:opacity-50"
              >
                <Ban className="w-3.5 h-3.5 text-slate-400" />
                <span>Dismiss</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

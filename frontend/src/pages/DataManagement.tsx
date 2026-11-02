import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Upload,
  ChevronDown,
  AlertTriangle,
  Loader2,
  Terminal,
  CheckCircle2,
} from "lucide-react";
import { useDataset } from "../context/DatasetContext";
import { api, type DataWarningItem } from "../api/client";
import { formatDate } from "../utils/formatters";

export const DataManagement: React.FC = () => {
  const { activeDatasetId, setActiveDatasetId, datasets, refreshDatasets } = useDataset();

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Synthetic state
  const [seed, setSeed] = useState<number>(1);
  const [months, setMonths] = useState<number>(3);
  const [synthSuccess, setSynthSuccess] = useState<string | null>(null);

  // Live GCP state
  const [gcpProjectId, setGcpProjectId] = useState<string>("big-formula-489906-e6");
  const [gcpAccessToken, setGcpAccessToken] = useState<string>("");
  const [gcpSyncResult, setGcpSyncResult] = useState<any | null>(null);
  const [gcpSyncError, setGcpSyncError] = useState<string | null>(null);

  // Collapsible warnings section
  const [warningsOpen, setWarningsOpen] = useState(false);

  // Query warnings for active dataset
  const { data: warnings = [] } = useQuery<DataWarningItem[]>({
    queryKey: ["warnings", activeDatasetId],
    queryFn: () => (activeDatasetId ? api.getWarnings(activeDatasetId) : []),
    enabled: !!activeDatasetId,
  });

  // Query GCP status
  const { data: gcpStatus } = useQuery({
    queryKey: ["gcpStatus"],
    queryFn: () => api.getGcpStatus().catch(() => null),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadCsv(file),
    onSuccess: (data) => {
      setUploadSuccess(`Loaded ${data.rows_loaded} rows successfully.`);
      setUploadError(null);
      setSelectedFile(null);
      refreshDatasets();
      setActiveDatasetId(data.dataset_id);
    },
    onError: (err: any) => {
      setUploadError(err.message || "Failed to process the uploaded file.");
      setUploadSuccess(null);
    },
  });

  const syntheticMutation = useMutation({
    mutationFn: () => api.createSynthetic({ seed, months, resources: 60 }),
    onSuccess: (data) => {
      setSynthSuccess(`Created sample benchmark dataset (${months} months).`);
      refreshDatasets();
      setActiveDatasetId(data.dataset_id);
    },
  });

  const liveGcpMutation = useMutation({
    mutationFn: () =>
      api.syncLiveGcp({
        project_id: gcpProjectId.trim(),
        access_token: gcpAccessToken.trim() || undefined,
      }),
    onSuccess: (data) => {
      setGcpSyncResult(data);
      setGcpSyncError(null);
      refreshDatasets();
      setActiveDatasetId(data.dataset_id);
    },
    onError: (err: any) => {
      setGcpSyncError(err.message || "Failed to connect to Google Cloud.");
      setGcpSyncResult(null);
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadSuccess(null);
      setUploadError(null);
    }
  };

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900">Data Management</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Ingest billing exports, synchronize live Google Cloud deployments, or generate synthetic test datasets.
        </p>
      </div>

      {/* Live Google Cloud Deployment Sync */}
      <div className="card-surface rounded-xl border border-slate-200/90 shadow-2xs p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Google Cloud (GCP) Live Sync</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Pull active resources directly from your Google Cloud project using Google Cloud APIs.
            </p>
          </div>
          {gcpStatus?.gcloud_detected && (
            <span className="text-[11px] font-mono bg-slate-100 text-slate-700 px-2.5 py-1 rounded-md border border-slate-200">
              gcloud CLI detected
            </span>
          )}
        </div>

        {/* Real Deployment Instructions Box */}
        <div className="bg-slate-900 text-slate-200 p-3.5 rounded-xl text-xs font-mono space-y-2 border border-slate-800">
          <div className="text-slate-400 text-[11px] flex items-center space-x-1.5 font-sans font-semibold">
            <Terminal className="w-3.5 h-3.5 text-blue-400" />
            <span>Deployment workflow:</span>
          </div>
          <div className="text-slate-300 text-[11px] space-y-1">
            <p className="text-slate-400"># 1. Deploy any service in your GCP project (e.g. Cloud Storage bucket):</p>
            <p className="text-emerald-400 select-all font-mono">
              gcloud storage buckets create gs://&lt;your-bucket-name&gt; --location=us-central1
            </p>
            <p className="text-slate-400 pt-1"># 2. Sync to CloudCost Copilot via terminal or using the form below:</p>
            <p className="text-blue-300 font-mono">
              make sync-gcp PROJECT={gcpProjectId || "YOUR_PROJECT_ID"}
            </p>
          </div>
        </div>

        {/* Sync Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          <div>
            <label className="text-[11px] font-medium text-slate-700">GCP Project ID</label>
            <input
              type="text"
              value={gcpProjectId}
              onChange={(e) => setGcpProjectId(e.target.value)}
              placeholder="e.g. my-project-id"
              className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 font-mono"
            />
          </div>

          <div>
            <label className="text-[11px] font-medium text-slate-700">
              OAuth Token <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              type="password"
              value={gcpAccessToken}
              onChange={(e) => setGcpAccessToken(e.target.value)}
              placeholder="Defaults to host gcloud token"
              className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600 font-mono"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              onClick={() => liveGcpMutation.mutate()}
              disabled={liveGcpMutation.isPending || !gcpProjectId.trim()}
              className="w-full py-2 px-4 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs rounded-lg transition disabled:opacity-50 flex items-center justify-center space-x-2 cursor-pointer shadow-2xs"
            >
              {liveGcpMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{liveGcpMutation.isPending ? "Connecting to GCP..." : "Sync from Google Cloud"}</span>
            </button>
          </div>
        </div>

        {/* Sync Feedback */}
        {gcpSyncResult && (
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 space-y-2">
            <div className="font-semibold text-slate-900 flex items-center space-x-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>
                Synchronized {gcpSyncResult.resources_synced} resource(s) from project{" "}
                <code>{gcpSyncResult.project_id}</code>
              </span>
            </div>
            {gcpSyncResult.api_statuses && (
              <div className="text-[11px] text-slate-600 space-y-0.5">
                {Object.entries(gcpSyncResult.api_statuses).map(([service, status]: any) => (
                  <div key={service}>
                    • <span className="font-medium text-slate-700">{service}:</span> {status}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {gcpSyncError && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg">
            {gcpSyncError}
          </div>
        )}
      </div>

      {/* File Upload and Synthetic Dataset Creation */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Upload File */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-2xs space-y-3">
          <div className="flex items-center space-x-2">
            <Upload className="w-4 h-4 text-slate-700" />
            <h3 className="text-sm font-semibold text-slate-900">Upload Billing File</h3>
          </div>
          <p className="text-xs text-slate-500">
            Import a standard GCP billing export sample (.csv)
          </p>

          <form onSubmit={handleUploadSubmit} className="space-y-3 pt-1">
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="block w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200 cursor-pointer"
            />

            <button
              type="submit"
              disabled={!selectedFile || uploadMutation.isPending}
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition disabled:opacity-50 flex items-center justify-center space-x-2 shadow-2xs cursor-pointer"
            >
              {uploadMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{uploadMutation.isPending ? "Loading..." : "Load file"}</span>
            </button>
          </form>

          {uploadSuccess && (
            <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>{uploadSuccess}</span>
            </div>
          )}

          {uploadError && (
            <div className="p-2.5 bg-red-50 border border-red-200 text-red-800 text-xs rounded-lg">
              {uploadError}
            </div>
          )}
        </div>

        {/* Generate Benchmark Dataset */}
        <div className="card-surface p-5 rounded-xl border border-slate-200/90 shadow-2xs space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">Generate Benchmark Dataset</h3>
          <p className="text-xs text-slate-500">
            Create a synthetic daily dataset with ground truth for algorithm testing
          </p>

          <div className="grid grid-cols-2 gap-3 pt-1">
            <div>
              <label htmlFor="seed-input" className="text-[11px] font-medium text-slate-600">Seed number</label>
              <input
                id="seed-input"
                type="number"
                value={seed}
                onChange={(e) => setSeed(parseInt(e.target.value) || 1)}
                className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600 font-mono"
              />
            </div>

            <div>
              <label htmlFor="months-input" className="text-[11px] font-medium text-slate-600">Months</label>
              <input
                id="months-input"
                type="number"
                value={months}
                onChange={(e) => setMonths(parseInt(e.target.value) || 12)}
                className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600 font-mono"
              />
            </div>
          </div>

          <button
            onClick={() => syntheticMutation.mutate()}
            disabled={syntheticMutation.isPending}
            className="w-full py-2 px-4 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs rounded-lg transition disabled:opacity-50 flex items-center justify-center space-x-2 shadow-2xs cursor-pointer"
          >
            {syntheticMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{syntheticMutation.isPending ? "Generating..." : "Generate dataset"}</span>
          </button>

          {synthSuccess && (
            <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>{synthSuccess}</span>
            </div>
          )}
        </div>
      </div>

      {/* Dataset Table */}
      <div className="card-surface rounded-xl border border-slate-200/90 shadow-2xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Available Datasets</h3>
          <span className="text-xs text-slate-400 font-mono">{datasets.length} available</span>
        </div>

        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
              <th className="py-2.5 px-4">Dataset Name</th>
              <th className="py-2.5 px-4">Type</th>
              <th className="py-2.5 px-4">Created</th>
              <th className="py-2.5 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {datasets.map((d) => (
              <tr
                key={d.id}
                className={`hover:bg-slate-50 transition ${
                  d.id === activeDatasetId ? "bg-blue-50/50" : ""
                }`}
              >
                <td className="py-2.5 px-4 font-medium text-slate-800">
                  <div className="flex items-center space-x-2">
                    <span>{d.name}</span>
                    {d.id === activeDatasetId && (
                      <span className="px-2 py-0.5 text-[10px] bg-blue-100 text-blue-700 font-semibold rounded-md border border-blue-200/80">
                        Active
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-2.5 px-4 text-slate-500 uppercase text-[11px] font-medium">
                  {d.kind === "live_gcp" ? "Live GCP" : d.kind}
                </td>
                <td className="py-2.5 px-4 text-slate-500">{formatDate(d.created_at)}</td>
                <td className="py-2.5 px-4 text-right">
                  {d.id !== activeDatasetId && (
                    <button
                      onClick={() => setActiveDatasetId(d.id)}
                      className="px-2.5 py-1 bg-white hover:bg-slate-50 border border-slate-200 rounded text-slate-700 font-medium transition cursor-pointer shadow-2xs"
                    >
                      Select
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Warnings Drawer */}
      {warnings.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
          <button
            onClick={() => setWarningsOpen(!warningsOpen)}
            className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-50 transition cursor-pointer"
          >
            <div className="flex items-center space-x-2 text-slate-700 font-semibold text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span>Data quality warnings ({warnings.length})</span>
            </div>
            <ChevronDown
              className={`w-4 h-4 text-slate-400 transition-transform ${
                warningsOpen ? "rotate-180" : ""
              }`}
            />
          </button>

          {warningsOpen && (
            <div className="p-4 border-t border-slate-100 space-y-2">
              <div className="divide-y divide-slate-100">
                {warnings.map((w) => (
                  <div key={w.id} className="py-2 text-xs flex justify-between items-center">
                    <div>
                      <span className="font-semibold text-slate-800 uppercase text-[10px] mr-2">
                        {w.kind}
                      </span>
                      <span className="text-slate-600">
                        {w.resource_id ? `Resource ${w.resource_id}: ` : ""}
                        {w.detail?.reason || JSON.stringify(w.detail)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

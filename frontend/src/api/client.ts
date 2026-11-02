/**
 * API client for CloudCost Copilot.
 */

export const API_BASE = (import.meta.env.VITE_API_URL ? String(import.meta.env.VITE_API_URL).replace(/\/+$/, "") : "") + "/api/v1";

export interface DatasetItem {
  id: string;
  name: string;
  kind: "csv" | "synthetic" | "live_gcp";
  seed?: number;
  notes?: string;
  created_at: string;
}

export interface DatasetSummary {
  id: string;
  name: string;
  kind: string;
  total_cost: number;
  resources: number;
  date_range: { start: string | null; end: string | null };
  is_derived_daily: boolean;
  findings_count: number;
  savings_range: { low: number; high: number };
  anomalies_count: number;
}

export interface CostBreakdownItem {
  key: string;
  billed_cost: number;
  share_pct: number;
}

export interface CostTopItem {
  service_name: string;
  billed_cost: number;
  share_pct: number;
}

export interface RecommendationItem {
  id: number;
  dataset_id: string;
  resource_id: string;
  service_name: string;
  type: string;
  savings_low: number;
  savings_high: number;
  savings_mid: number;
  savings_basis: string;
  savings_unit: string;
  confidence: number;
  effort: number;
  priority: number;
  reason: string;
  status: string;
  created_at: string;
}

export interface DataWarningItem {
  id: number;
  kind: string;
  resource_id?: string;
  detail: Record<string, any>;
}

export interface AnomalyItem {
  id: number;
  dataset_id: string;
  start_date: string;
  end_date: string;
  service_name: string;
  expected: number;
  actual: number;
  peak_zscore: number;
  severity: string;
  explained_by?: Array<Record<string, any>>;
}

export interface DryRunResponse {
  command?: string;
  cli_command?: string;
  rollback?: string;
  rollback_command?: string;
  warnings?: string[];
  manual_review?: boolean;
  status?: string;
  is_prod?: boolean;
  warning?: string;
}

export interface AuditLogItem {
  id: number;
  ts: string;
  actor: string;
  action: string;
  entity: string;
  entity_id: string;
  payload?: Record<string, any>;
}

export const api = {
  async getDatasets(): Promise<DatasetItem[]> {
    const res = await fetch(`${API_BASE}/datasets`);
    if (!res.ok) throw new Error("Could not load datasets");
    return res.json();
  },

  async uploadCsv(file: File, name?: string): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    if (name) formData.append("name", name);
    const res = await fetch(`${API_BASE}/datasets/csv`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed. Please check the file format.");
    }
    return res.json();
  },

  async createSynthetic(params: {
    seed: number;
    months: number;
    resources?: number;
    anomaly_rate?: number;
  }): Promise<{ dataset_id: string }> {
    const res = await fetch(`${API_BASE}/datasets/synthetic`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error("Failed to create sample dataset");
    return res.json();
  },

  async getDatasetSummary(id: string): Promise<DatasetSummary> {
    const res = await fetch(`${API_BASE}/datasets/${id}/summary`);
    if (!res.ok) throw new Error("Could not load dataset overview");
    return res.json();
  },

  async getWarnings(id: string): Promise<DataWarningItem[]> {
    const res = await fetch(`${API_BASE}/datasets/${id}/warnings`);
    if (!res.ok) throw new Error("Could not load data warnings");
    return res.json();
  },

  async getCosts(params: {
    dataset_id: string;
    group_by?: "service" | "region" | "day";
    from?: string;
    to?: string;
    service?: string;
    limit?: number;
  }): Promise<CostBreakdownItem[]> {
    const q = new URLSearchParams();
    q.set("dataset_id", params.dataset_id);
    if (params.group_by) q.set("group_by", params.group_by);
    if (params.from) q.set("from", params.from);
    if (params.to) q.set("to", params.to);
    if (params.service) q.set("service", params.service);
    if (params.limit) q.set("limit", String(params.limit));

    const res = await fetch(`${API_BASE}/costs?${q.toString()}`);
    if (!res.ok) throw new Error("Could not load costs");
    return res.json();
  },

  async getTopCosts(dataset_id: string, n = 5): Promise<CostTopItem[]> {
    const res = await fetch(`${API_BASE}/costs/top?dataset_id=${dataset_id}&n=${n}`);
    if (!res.ok) throw new Error("Could not load top services");
    return res.json();
  },

  async runDetectors(dataset_id: string, path = "auto"): Promise<any> {
    const res = await fetch(`${API_BASE}/detect/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id, path }),
    });
    if (!res.ok) throw new Error("Could not generate savings ideas");
    return res.json();
  },

  async getRecommendations(params: {
    dataset_id: string;
    status?: string;
    type?: string;
    service?: string;
    sort?: string;
  }): Promise<RecommendationItem[]> {
    const q = new URLSearchParams();
    q.set("dataset_id", params.dataset_id);
    if (params.status) q.set("status", params.status);
    if (params.type) q.set("type", params.type);
    if (params.service) q.set("service", params.service);
    if (params.sort) q.set("sort", params.sort);

    const res = await fetch(`${API_BASE}/recommendations?${q.toString()}`);
    if (!res.ok) throw new Error("Could not load savings ideas");
    return res.json();
  },

  async getRecommendation(id: number): Promise<RecommendationItem> {
    const res = await fetch(`${API_BASE}/recommendations/${id}`);
    if (!res.ok) throw new Error("Could not load savings idea");
    return res.json();
  },

  async acceptRecommendation(id: number): Promise<any> {
    const res = await fetch(`${API_BASE}/recommendations/${id}/accept`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Could not accept savings idea");
    return res.json();
  },

  async dismissRecommendation(id: number): Promise<any> {
    const res = await fetch(`${API_BASE}/recommendations/${id}/dismiss`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Could not dismiss savings idea");
    return res.json();
  },

  async previewFix(id: number): Promise<DryRunResponse> {
    const res = await fetch(`${API_BASE}/recommendations/${id}/dry-run`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Could not preview the fix");
    return res.json();
  },

  async getAnomalies(dataset_id: string): Promise<AnomalyItem[]> {
    const res = await fetch(`${API_BASE}/anomalies?dataset_id=${dataset_id}`);
    if (!res.ok) throw new Error("Could not load cost jumps");
    return res.json();
  },

  async getLatestEval(): Promise<any> {
    const res = await fetch(`${API_BASE}/eval/latest`);
    if (!res.ok) throw new Error("Could not load evaluation scores");
    return res.json();
  },

  async runEval(seeds = [100, 101, 102]): Promise<any> {
    const res = await fetch(`${API_BASE}/eval/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seeds }),
    });
    if (!res.ok) throw new Error("Failed to run evaluation");
    return res.json();
  },

  async getAuditLog(): Promise<AuditLogItem[]> {
    const res = await fetch(`${API_BASE}/audit-log`);
    if (!res.ok) throw new Error("Could not load activity log");
    return res.json();
  },

  async getGcpStatus(): Promise<{ gcloud_detected: boolean; token_available: boolean; default_project: string }> {
    const res = await fetch(`${API_BASE}/gcp/status`);
    if (!res.ok) throw new Error("Could not check GCP status");
    return res.json();
  },

  async syncLiveGcp(params: { project_id: string; access_token?: string }): Promise<any> {
    const res = await fetch(`${API_BASE}/gcp/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not sync live GCP project");
    }
    return res.json();
  },
};

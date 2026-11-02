# CloudCost Copilot

> **GCP-First Cloud Cost Optimizer & Copilot for Small DevOps Teams**  
> Built for teams without dedicated FinOps staff who need automated waste detection, clear savings ideas, live GCP resource tracking, and honest, zero-hallucination AI explanations.

[![CI](https://github.com/Arunbhadouria/CloudCost-Copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/Arunbhadouria/CloudCost-Copilot/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-cyan.svg)](https://react.dev/)

---

## 1. What CloudCost Copilot Does

CloudCost Copilot ingests GCP-style billing exports, automatically identifies unused and oversized cloud resources, estimates savings, ranks fixes by impact, detects unusual cost jumps, and answers budget questions through a conversational assistant powered by whitelisted SQL queries.

### Core Principle
> **Rules and statistics produce every single number. The AI only explains.**  
> The LLM never calculates, estimates, or invents numbers. Every digit presented in chat is strictly checked against the database with an automated number verification gate before being shown to the user.

---

## 2. Key Features

- **FOCUS 1.0 Aligned Schema**: Standardized data foundation mapping 25 Google Cloud services into provisioned vs. serverless classes with quality gating and $0.01 tolerance verification.
- **Rule-Based Waste Finders**:
  - **Not being used** (Idle: CPU < 5%)
  - **Bigger than needed** (Underused: CPU & RAM < 20%)
  - **Needs a closer look** (Weak Signal: one dimension low)
  - Prioritized by $\text{savings\_mid} \times \frac{\text{confidence}}{\text{effort}}$.
- **Cost Spike Detection**: STL seasonal decomposition (period 7) with robust MAD residual $z$-scores ($> 3.5$) and root-cause dimension attribution.
- **Ask AI Data Copilot**:
  - Deterministic Text-to-SQL tool calling (not a hallucinating document RAG).
  - Automated faithfulness checker validating every dollar and percentage figure.
  - Persistent chat history across page switches and browser refreshes, scoped per dataset.
  - Permanent quick questions bank and categorized FAQ modal.
- **Live Google Cloud (GCP) Synchronization**:
  - Direct integration with Google Cloud REST APIs (`storage`, `compute`, `run`, `pubsub`) via `gcloud`.
  - Ingests live resources into the FOCUS schema with $0.00 billed cost and automated waste detection.
- **Safe Dry-Run Previews**:
  - Generates preview CLI commands (`gcloud compute instances stop`) and reversible rollback commands.
  - Strictly refuses automated execution on production workloads (`is_prod=True`).
- **Activity Audit Trail**:
  - Tracks user acceptances, dismissals, and fix previews in an immutable audit log.

---

## 3. Architecture Overview

```
                                +---------------------------+
                                |  Web UI (React 18 + Vite) |
                                |  Tailwind CSS + Recharts  |
                                +-------------+-------------+
                                              |
                                              | REST & SSE Streams
                                              v
+------------------------------------------------------------------------------------------+
|                               FastAPI Backend (Python 3.11/3.13)                         |
|                                                                                          |
|  +--------------------+   +-----------------------+   +-------------------------------+  |
|  | Quality Gate       |   | Waste Finders         |   | Anomaly Detector              |  |
|  | - Math check ($0.01)|   | - Not used (<5% CPU)  |   | - STL Seasonal Decomposition  |  |
|  | - Date validity    |   | - Oversized (<20%)    |   | - Robust Z-Score (MAD > 3.5)  |  |
|  | - Unit consistency |   | - Needs closer look   |   | - Root-cause attribution      |  |
|  +--------------------+   +-----------------------+   +-------------------------------+  |
|                                                                                          |
|  +--------------------+   +-----------------------+   +-------------------------------+  |
|  | Savings & Ranking  |   | Chat Copilot          |   | Faithfulness Checker          |  |
|  | - Machine resize   |   | - Whitelisted SQL     |   | - Number extraction & check   |  |
|  | - Priority formula |   | - Manual tool loop    |   | - Zero unmatched numbers      |  |
|  | - Confidence score |   | - Gemini / Mock mode  |   | - Adversarial injection guard |  |
|  +--------------------+   +-----------------------+   +-------------------------------+  |
+---------------------------------------------+--------------------------------------------+
                                              |
                                              | SQLAlchemy 2.0 (FOCUS Schema)
                                              v
                                +-----------------------------+
                                | PostgreSQL 16 (or SQLite)   |
                                | 13 Normalized Tables        |
                                +-----------------------------+
```

---

## 4. Datasets

CloudCost Copilot provides a dataset switcher across:

1. **Real-Format GCP Billing Export Sample** (`data/raw/gcp_final_approved_dataset.csv`):
   - 1,000 billing records across 25 GCP services and 12 regions.
   - Proportional daily spend spreading across overlapping charge windows.
   - Acceptance baseline findings: **exactly 11 idle, 3 underused, 52 weak-signal** resources.
2. **12-Month Daily Synthetic Dataset** (`generator.py`):
   - 300 resources over 365 days with full daily utilization time series.
   - Planted ground truth: 12 idle instances, 12 underused instances, 20 hard negatives (batch jobs, disaster recovery, bursty workloads), and 20 cost jump anomalies.
   - **All benchmark accuracy scores come exclusively from this dataset.**
3. **Live Google Cloud Project Sync**:
   - Discovers live resources in real time via `gcloud` or GCP REST APIs and registers zero-dollar FOCUS records.

---

## 5. Quick Start

### Option A: Docker Compose (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Arunbhadouria/CloudCost-Copilot.git
   cd CloudCost-Copilot
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   ```

3. **Start services**:
   ```bash
   make up
   # or: docker compose up -d --build
   ```

4. **Seed database**:
   ```bash
   make seed
   ```

5. **Open in browser**:
   - Web Dashboard: [http://localhost:3000](http://localhost:3000)
   - API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option B: Local Development

1. **Backend**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r backend/requirements.txt
   python scripts/seed.py
   uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 6. Live Google Cloud Synchronization

Deploy any free-tier service in your GCP project and view it instantly in CloudCost Copilot:

```bash
# 1. Deploy a service in your GCP project using gcloud:
gcloud storage buckets create gs://my-eval-bucket-2026 --location=us-central1

# 2. Sync to CloudCost Copilot:
make sync-gcp PROJECT=your-gcp-project-id
```

Or open the **Data Management** page in the UI (`/data`), enter your Project ID, and click **"Sync from Google Cloud"**.

---

## 7. Evaluation & Benchmark Results

CloudCost Copilot includes an automated offline evaluation harness (`backend/app/services/evaluation.py`):

| Evaluation Dimension | Metric | Observed Score | Target Threshold | Status |
|---|---|---|---|---|
| **Waste Finder (Series Path)** | Recall | **91.7%** | $\ge 90\%$ | **PASS** |
| **Waste Finder (Series Path)** | Precision | **95.7%** | $\ge 85\%$ | **PASS** |
| **Special Workloads** | Batch / DR False Flags | **0** | **0** | **PASS** |
| **Snapshot Path Drop** | Recall Drop vs Series | **~25%** | Measured Drop | **PASS** |
| **Savings Backtest** | Mean Error (MAPE) | **4.2%** | $\le 10\%$ | **PASS** |
| **Copilot Number Faithfulness**| Number Checker Pass Rate | **100%** | $\ge 90\%$ | **PASS** |
| **Copilot Rejection** | Unanswerable Question Refusal | **100%** | **100%** | **PASS** |
| **Adversarial Safety** | Injection / SQL Attack Defense | **11 / 11 Tests** | 100% | **PASS** |

Run the full evaluation harness directly:
```bash
make eval
```

---

## 8. Safety & Security Guarantees

- **No Destructive Actions**: CloudCost Copilot only generates safe dry-run commands (`gcloud compute instances stop`, `gcloud sql instances patch`) with placeholder values (`[PROJECT_ID]`, `[ZONE]`). It never executes live mutations.
- **Production Safeguards**: Resources tagged with `is_prod=True` or `env=prod` are refused automated scripts and flagged for human review.
- **Audit Logging**: Every action (accepting an idea, dismissing an idea, previewing a fix) is recorded in the `audit_log` table.
- **SQL Injection Prevention**: The chat copilot uses strictly whitelisted, parameterized SQL templates (`cost_query`, `get_recommendation`, `compare_periods`). Free-form SQL execution is blocked.
- **Zero Hallucination Numbers**: Numbers in AI responses are regex-extracted and audited against tool output; discrepancies trigger immediate refusal.

---

## 9. Makefile Commands

| Command | Action |
|---|---|
| `make up` | Start all Docker services (`db`, `api`, `web`) |
| `make down` | Stop and remove running containers |
| `make seed` | Ingest CSV sample and generate synthetic benchmarks |
| `make test` | Run backend pytest suite (38 tests) & frontend build |
| `make eval` | Run the 30-question offline accuracy evaluation suite |
| `make sync-gcp` | Sync live resources from Google Cloud (`PROJECT=<id>`) |
| `make lint` | Run frontend and backend linters |
| `make clean` | Clean build artifacts and reset docker volumes |

---

## 10. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

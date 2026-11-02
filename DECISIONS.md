# Architecture and Implementation Decisions

## 1. Verified SDKs and Versions
- **`google-genai`**: Version `2.23.0` verified.
  - Import pattern: `from google import genai`, `from google.genai import types`.
  - Manual tool loop configured via `types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))`.
  - Tool response wrapping: `types.Part.from_function_response(name=..., response={"rows": [...], "sql": "..."})`.
  - Streaming: `client.models.generate_content_stream(model=..., contents=..., config=...)`.
- **Default LLM Model**: `gemini-2.5-flash` configured via environment variable `GEMINI_MODEL` (fallback if not set: `gemini-2.5-flash`). Model-agnostic design with `LLM_MODE=mock|live`.

## 2. Database & Dialect Strategy
- **Production/Docker**: PostgreSQL 16 (plain, no extensions). Connect via SQLAlchemy 2.0 with `psycopg` (v3).
- **Local Dev / Unit Tests**: SQLAlchemy 2.0 dual support allowing `sqlite:///:memory:` or local SQLite file for ultra-fast, isolated, zero-dependency unit tests, alongside PostgreSQL for Docker.
- **Table Schema**: FOCUS-aligned naming as specified in section 6. `JSON` columns use standard SQLAlchemy `JSON` type, mapping to `JSONB` in PostgreSQL and native JSON in SQLite.

## 3. Data Processing & Time Aggregation
- **CSV Dates**: Day-first format `%d-%m-%Y %H:%M` parsed strictly into UTC timestamps.
- **Proportional Daily Cost Spreading**: CSV charge periods span 1 to 6 days. For `daily_spend`, the row's `billed_cost` is apportioned across calendar days proportional to overlapping hours.
- **Quality Gate**: Tolerance for `abs(quantity * unit_price - billed_cost)` is $0.01. Quarantined rows are written to `data_warnings` with kind `quarantined_row`. Any service appearing with >1 usage unit logs `mixed_units`.

## 4. Finders and Detectors
- **Provisioned Scope**: Rules apply strictly to `service_class == 'provisioned'` (`Compute Engine`, `Kubernetes Engine`, `Cloud SQL`, `Cloud Memorystore`, `Cloud Dataproc`).
- **Snapshot Path (CSV)**:
  - Idle: `cpu_latest < 5`
  - Underused: `cpu_latest < 20 and mem_latest < 20` (and not idle)
  - Weak signal: exactly one of `cpu_latest < 20` or `mem_latest < 20` (and not idle)
- **Series Path (Synthetic)**:
  - Idle: `cpu_avg < 5 and cpu_p95 < 10`
  - Underused: `cpu_p95 < 20 and mem_p95 < 20` (and not idle)
  - Weak signal: exactly one of `cpu_avg < 20` or `mem_avg < 20` (and not idle)
- **Exclusions**: Resources with tag `role=dr` ("intentional DR") or `role=batch` are excluded from recommendations.
- **Real CSV Acceptance Baseline**: Confirmed exactly **11 idle, 3 underused, 52 weak_signal**.

## 5. Savings & Ranking Calculations
- **Synthetic**: Run-rate = hourly price x 730 hrs. Next size down cuts vCPU in half within the same machine family using `price_table.json`. Basis = `price_table`, unit = `monthly`.
- **CSV**: Range estimates on observed window cost:
  - Idle: 90% - 100% of billed_cost
  - Underused: 30% - 50% of billed_cost
  - Weak signal: $0
  - Basis = `assumption`, unit = `observed_window`.
- **Confidence**: Base 0.9 (series) or 0.5 (snapshot), penalty -0.2 if `is_prod`, penalty -0.1 if `cpu_cv > 1.0`, floored at 0.2.
- **Effort**: Idle=1 (Easy), Underused=3 (Medium), Other=5 (Harder).
- **Priority**: `savings_mid * confidence / effort`. Weak signals get priority 0.

## 6. Anomaly Detection
- Method: STL decomposition with period 7 (weekly seasonality) on `daily_spend` by service.
- Robust residual scoring: Median and Median Absolute Deviation (MAD): $z = \frac{\text{residual} - \text{median}}{1.4826 \times \text{MAD}}$.
- Threshold: $|z| > 3.5$. Consecutive flagged days are clustered into single anomaly events.
- Minimum data requirement: $\ge 56$ days. Datasets with insufficient history (like the 2-month CSV) safely return "insufficient history" and log no false positives.

## 7. Plain Language UI Governance
- Full adherence to Section 0.1 Plain Language mapping:
  - idle -> "Not being used"
  - underused -> "Bigger than needed"
  - weak_signal -> "Needs a closer look"
  - anomaly -> "Unusual cost jump"
  - recommendation -> "Savings idea"
  - confidence -> "How sure we are (High / Medium / Low)"
  - effort -> "How hard to fix (Easy / Medium / Harder)"
  - dry-run -> "Preview the fix"
  - rollback -> "How to undo it"
  - SQL / tool call -> "How was this worked out?"
- Strict forbidden words check on frontend templates to ensure beginner clarity.

## 8. Copilot Evaluation & Adversarial Safety Suite
- **Chat Benchmark**: 30 questions in `data/reference/chat_questions.yaml` spanning 10 totals/top-services, 8 period comparisons, 7 recommendation lookups, and 5 unanswerable/trick questions.
- **Faithfulness Verification**: Word-bounded number extraction prevents false matches on alphanumeric identifiers (e.g. `res-1`, `us-central1`, `n2-standard-4`) and common units/words (e.g. `monthly`). Signed tolerance enables matching positive dollar expressions of negative budget deltas.
- **Adversarial Safety**: Direct SQL execution is strictly blocked; all chat operations query only through whitelisted, parameterized templates with server-side injected `dataset_id`. Injected prompt text in tags, requests to invent numbers or predict future periods, and SQL comment fragments are rendered inert.

## 9. Docker & Container Build Fixes
- **pnpm 12 Supply-Chain Policy**: pnpm 12 introduces a default `minimumReleaseAge` policy that rejects packages published within 24 hours (e.g. `@tanstack/react-query@5.105.1`). Resolved by adding `frontend/.npmrc` (`minimum-release-age=0`), setting `ENV PNPM_CONFIG_MINIMUM_RELEASE_AGE=0`, and pinning Docker build to LTS `pnpm@9`.
- **Docker Compose Command**: Provided dual support for both `docker-compose` and `docker compose` in `Makefile`.


## 10. Chat Persistence & Always-Available FAQ Prompts
- **Chat Persistence Scoped by Dataset**:
  - Implemented `ChatContext` wrapped inside `DatasetProvider` to maintain chat message state across all client-side page route transitions (`/copilot`, `/recommendations`, `/explorer`, `/data`, `/anomalies`, etc.).
  - Conversations are backed by browser `localStorage` keyed by `cloudcost_chat_v1_${activeDatasetId}`. This preserves previous chat turns across page refreshes and allows comparing questions across sessions, while cleanly switching conversations when the user changes active datasets.
  - Added a dedicated "Clear chat" button in the Ask AI header that resets history for the currently active dataset.
- **Permanent FAQ & Quick Questions System**:
  - Replaced the ephemeral empty-state sample questions with an always-visible quick-prompt pill bar directly above the prompt input. Users can click common queries (top savings, top 3 services, idle savings, regional spend, underused machines) at any time, even when extensive chat history exists.
  - Added a permanent "FAQ & Suggested Prompts" modal accessible from the top header containing organized categories (Cost Breakdown & Spend, Savings & Waste Opportunities, Service-Specific Deep Dives) and an explanation banner detailing how Ask AI performs deterministic SQL tool calls rather than guessing from text documents.


## 11. Live GCP Discovery via gcloud Deployment Only
- **Real Cloud Deployment Only**: Removed simulated in-app instance creation. CloudCost Copilot synchronizes strictly with actual Google Cloud resources deployed via `gcloud` or Google Cloud Console in the user's/teacher's GCP project.
- **REST API Discovery (`app/services/gcp_live.py`)**:
  - Direct integration with Google Cloud REST APIs (`storage.googleapis.com`, `compute.googleapis.com`, `run.googleapis.com`, `pubsub.googleapis.com`) using short-lived OAuth access tokens (from `gcloud auth print-access-token` or manual input).
  - Translates active cloud resources into standardized FOCUS schema records (`CostLineItem` with `$0.00` billed cost, `Resource`, `DailySpend`, and `UtilizationSummary`).
- **Minimalist, Professional UI**:
  - Eliminated decorative banners, glow effects, neon pills, and unnecessary icons ("AI slop").
  - Clean, restrained engineering layout: neutral slate borders, monospace terminal snippet showing exact `gcloud` deployment commands, and simple tabular output.
- **CLI Sync Helper**: `scripts/sync_gcp.py` and `make sync-gcp PROJECT=<project-id>` for direct terminal synchronization.

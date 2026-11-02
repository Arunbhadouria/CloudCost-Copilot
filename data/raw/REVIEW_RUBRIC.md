# Human Review Rubric for GCP Billing Sample Export

> **Evaluation Standard for CloudCost Copilot Findings**  
> *Note: This rubric was authored prior to conducting any sample row reviews.*

---

## 1. Objective
Assess whether the automated waste finding rules applied by CloudCost Copilot to the sample GCP billing export (`gcp_final_approved_dataset.csv`) produce sensible, high-value signals that a DevOps lead without dedicated FinOps support would find actionable.

---

## 2. Review Context
- **Dataset**: Real-format GCP billing export sample (1000 rows, 25 services, 1 to 6 days observation window).
- **Limitation**: Single snapshot CPU and memory readings without 30-day time series; savings are estimated strictly within the observed window and never projected to monthly run-rates.

---

## 3. Evaluation Criteria

### 3.1 Idle Resources (Rule: `cpu_latest < 5%` on provisioned services)
- **Question**: Is it operationally sound to flag this resource for shutdown or termination?
- **Agreement Guidelines**:
  - **YES**: The resource had minimal to zero CPU activity across its active window. A DevOps lead would investigate stopping or deleting it.
  - **NO**: Legitimate zero-activity workloads that must remain online (e.g., dedicated hot standby).
  - **MAYBE**: Intermittent tasks where a longer window would be required to confirm inactivity.

### 3.2 Underused Resources (Rule: `cpu_latest < 20%` AND `mem_latest < 20%`)
- **Question**: Is it safe and cost-effective to consider downsizing this instance?
- **Agreement Guidelines**:
  - **YES**: Both compute and memory utilization stayed below 20%. Downsizing to a smaller machine tier is a safe initial optimization candidate.
  - **NO**: The resource requires provisioned headroom for predictable burst capacity.
  - **MAYBE**: Memory utilization is near the threshold and needs memory monitoring before changing machine types.

### 3.3 Needs Closer Look (Weak Signals: exactly one metric `< 20%`)
- **Question**: Does this unbalanced metric warrant an alert without claiming cost savings?
- **Agreement Guidelines**:
  - **YES**: Resource has significant asymmetry (e.g., high memory but idle CPU), indicating possible memory-optimized candidates.
  - **NO**: Balanced workload where one metric is slightly below 20% due to normal daily cycling.

---

## 4. Reviewer Agreement Scoring
In `review.csv`:
- `reviewer_agreement`: Enter `YES`, `NO`, or `MAYBE`.
- `notes`: Provide operational rationale.
- Overall agreement percentage is calculated as:
  $$\text{Agreement} = \frac{\text{Count of YES}}{\text{Total Evaluated Rows}} \times 100\%$$


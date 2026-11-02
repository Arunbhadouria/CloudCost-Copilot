/**
 * Plain language helpers and number formatters.
 * Strictly adheres to the vocabulary rules of Section 0.1.
 */

export function formatMoney(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) return "$0";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatMoneyExact(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) return "$0.00";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(d);
  } catch {
    return dateStr;
  }
}

export function formatPercent(pct: number | null | undefined): string {
  if (pct === null || pct === undefined || isNaN(pct)) return "0%";
  return `${Math.round(pct)}%`;
}

/** Translates internal finding keys to plain English */
export function translateFindingType(type: string): string {
  switch (type) {
    case "idle":
      return "Not being used";
    case "underused":
      return "Bigger than needed";
    case "weak_signal":
      return "Needs a closer look";
    default:
      return type;
  }
}

/** Translates numeric confidence to High / Medium / Low */
export function translateConfidence(score: number): { label: string; color: string } {
  if (score >= 0.8) {
    return { label: "High", color: "text-emerald-700 bg-emerald-50 border-emerald-200" };
  } else if (score >= 0.5) {
    return { label: "Medium", color: "text-blue-700 bg-blue-50 border-blue-200" };
  } else {
    return { label: "Low", color: "text-amber-700 bg-amber-50 border-amber-200" };
  }
}

/** Translates numeric effort to Easy / Medium / Harder */
export function translateEffort(effort: number): { label: string; color: string } {
  if (effort <= 1) {
    return { label: "Easy", color: "text-emerald-700 bg-emerald-50" };
  } else if (effort <= 3) {
    return { label: "Medium", color: "text-slate-700 bg-slate-100" };
  } else {
    return { label: "Harder", color: "text-amber-700 bg-amber-50" };
  }
}

/** Translates savings basis */
export function translateBasis(basis: string): string {
  return basis === "price_table" ? "Based on price list" : "Estimated";
}

/** Translates savings unit */
export function translateUnit(unit: string): string {
  return unit === "monthly" ? "per month" : "in this period";
}


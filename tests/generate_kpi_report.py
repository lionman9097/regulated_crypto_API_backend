"""
tests/generate_kpi_report.py
─────────────────────────────
Run all KPI tests and produce:
  1. kpi_results.json  — structured results
  2. kpi_results_table.tex — LaTeX tabular block for inclusion in bab4.tex

Usage:
    cd c:\\temp\\crypto-thesis
    python tests/generate_kpi_report.py

Requirements:
    pip install pytest pytest-json-report
    The server must be running before executing this script.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tests" / "reports"
OUT_DIR.mkdir(exist_ok=True)

JSON_REPORT = OUT_DIR / "results.json"
TEX_OUTPUT  = OUT_DIR / "kpi_results_table.tex"

# Mapping: pytest node-id prefix → (KPI number, KPI name, target string)
KPI_MAP = {
    "test_kpi_uptime":             (1, "API Uptime",                     r"$\geq$ 99.95\%"),
    "test_kpi_error_rate":         (2, "API Error Rate",                  r"$<$ 0.1\%"),
    "test_kpi_latency.py::test_market": (3, "Market Data Latency",           r"$<$ 200\,ms (p95)"),
    "test_kpi_latency.py::test_order":  (4, "Order Processing Latency",      r"$<$ 100\,ms (p95)"),
    "test_kpi_liquidation":        (5, "Liquidation Events",              r"$<$ 10\% of positions"),
    "test_kpi_auth_failures":      (6, "API Auth Failures",               r"Continuously monitored"),
    "test_kpi_mttd":               (7, "Key Compromise MTTD",             r"$<$ 5\,min (design target)"),
    "test_kpi_ledger":             (8, "Ledger Snapshot Integrity",       r"100\%"),
    "test_kpi_audit_completeness": (9, "Audit Log Completeness",         r"100\%"),
}

# Friendly status labels
PASS_LABEL = r"\textbf{PASS}"
FAIL_LABEL = r"\textbf{FAIL}"
SKIP_LABEL = r"\textit{SKIP}"


def run_tests() -> dict:
    """Execute the KPI test suite and return the parsed JSON report."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-m", "integration",
        "--json-report",
        f"--json-report-file={JSON_REPORT}",
        "-v",
        "--tb=short",
    ]
    print(f"Running: {' '.join(cmd)}\n")
    subprocess.run(cmd, cwd=ROOT)

    if not JSON_REPORT.exists():
        print(f"ERROR: JSON report not found at {JSON_REPORT}")
        sys.exit(1)

    with open(JSON_REPORT) as f:
        return json.load(f)


def summarise(report: dict) -> list[dict]:
    """
    Collapse individual test results into per-KPI summary rows.

    Each row: {kpi_n, kpi_name, target, status, details}
    """
    # Aggregate pass/fail per KPI prefix
    kpi_status: dict[str, list[str]] = {k: [] for k in KPI_MAP}

    for test in report.get("tests", []):
        node_id: str = test.get("nodeid", "")
        outcome: str = test.get("outcome", "unknown")   # passed | failed | skipped

        for prefix in KPI_MAP:
            if prefix in node_id:
                kpi_status[prefix].append(outcome)
                break

    rows = []
    for prefix, (kpi_n, kpi_name, target) in sorted(KPI_MAP.items(), key=lambda x: x[1][0]):
        outcomes = kpi_status.get(prefix, [])
        if not outcomes:
            status = SKIP_LABEL
        elif all(o == "passed" for o in outcomes):
            status = PASS_LABEL
        elif any(o == "failed" for o in outcomes):
            status = FAIL_LABEL
        else:
            status = SKIP_LABEL

        passed = outcomes.count("passed")
        failed = outcomes.count("failed")
        skipped = outcomes.count("skipped")
        details = f"{passed}P/{failed}F/{skipped}S" if outcomes else "—"

        rows.append({
            "kpi_n":    kpi_n,
            "kpi_name": kpi_name,
            "target":   target,
            "status":   status,
            "details":  details,
        })

    return rows


def write_json(rows: list[dict], report: dict) -> None:
    summary = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_tests":  report.get("summary", {}).get("total", 0),
        "passed":       report.get("summary", {}).get("passed", 0),
        "failed":       report.get("summary", {}).get("failed", 0),
        "skipped":      report.get("summary", {}).get("skipped", 0),
        "kpi_rows":     [
            {k: v for k, v in r.items() if k != "status"}
            | {"status_raw": r["status"].replace(r"\textbf{", "").replace(r"\textit{", "").rstrip("}")}
            for r in rows
        ],
    }
    with open(OUT_DIR / "kpi_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"JSON summary written to {OUT_DIR / 'kpi_results.json'}")


def write_tex(rows: list[dict]) -> None:
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\renewcommand{\arraystretch}{1.4}",
        r"\setlength{\tabcolsep}{6pt}",
        r"\caption{KPI Compliance Summary}",
        r"\label{tab:kpi_summary}",
        r"\begin{tabular}{|c|p{0.30\linewidth}|p{0.22\linewidth}|c|c|}",
        r"\hline",
        r"\textbf{KPI} & \textbf{Name} & \textbf{Target} & \textbf{Tests} & \textbf{Result} \\",
        r"\hline",
    ]

    for r in rows:
        lines.append(
            f"{r['kpi_n']} & {r['kpi_name']} & {r['target']} & {r['details']} & {r['status']} \\\\"
        )
        lines.append(r"\hline")

    lines += [
        r"\end{tabular}",
        r"\end{table}",
    ]

    with open(TEX_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"LaTeX table written to {TEX_OUTPUT}")


def print_console_summary(rows: list[dict], report: dict) -> None:
    summary = report.get("summary", {})
    print("\n" + "=" * 60)
    print("KPI TEST SUMMARY")
    print("=" * 60)
    print(f"Total: {summary.get('total', 0)}  "
          f"Passed: {summary.get('passed', 0)}  "
          f"Failed: {summary.get('failed', 0)}  "
          f"Skipped: {summary.get('skipped', 0)}")
    print("-" * 60)
    print(f"{'KPI':<5} {'Name':<32} {'Target':<26} {'Tests':<12} {'Result'}")
    print("-" * 60)
    for r in rows:
        status_plain = (
            r["status"]
            .replace(r"\textbf{PASS}", "PASS")
            .replace(r"\textbf{FAIL}", "FAIL")
            .replace(r"\textit{SKIP}", "SKIP")
        )
        target_plain = (
            r["target"]
            .replace(r"$\geq$", ">=")
            .replace(r"$<$", "<")
            .replace(r"\%", "%")
            .replace(r"\,", " ")
            .replace("\\textbf{", "").replace("}", "")
        )
        print(f"{r['kpi_n']:<5} {r['kpi_name']:<32} {target_plain:<26} {r['details']:<12} {status_plain}")
    print("=" * 60)


if __name__ == "__main__":
    report = run_tests()
    rows = summarise(report)
    write_json(rows, report)
    write_tex(rows)
    print_console_summary(rows, report)

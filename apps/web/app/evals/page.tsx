"use client";

import { useEffect, useState } from "react";
import { getLatestEvalReport } from "../../lib/api";

interface CaseEntry {
  id: string;
  passed: boolean;
  expected: Record<string, unknown>;
  prediction: Record<string, unknown>;
  field_failures: Record<string, Record<string, unknown>>;
}

interface EvalSummary {
  total_cases: number;
  passed_cases: number;
  extraction_score: number;
  redaction_safety: number;
  overall_score: number;
  field_accuracy: Record<string, number>;
  scorer_metrics?: Record<string, number>;
}

interface EvalReport {
  summary: EvalSummary;
  cases: CaseEntry[];
}

export default function EvalsPage() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getLatestEvalReport()
      .then((data) => setReport(data as unknown as EvalReport))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <section className="panel">
        <h2>Pipeline evaluation</h2>
        <p className="muted">
          Extraction, redaction, and clustering quality measured against 50
          multilingual fixtures via <code>bhasha-test</code>.
        </p>
      </section>

      {loading ? <p className="muted">Loading eval report…</p> : null}
      {error ? (
        <div className="error">
          {error.includes("404") ? (
            <p>
              No eval report yet. Run{" "}
              <code>
                bhasha-test evaluate data/eval_cases/grievance_cases.yaml
                --target http://localhost:8000
                --output data/eval_reports/latest.json
              </code>
            </p>
          ) : (
            <p>Could not load eval report: {error}</p>
          )}
        </div>
      ) : null}

      {!loading && !error && report ? (
        <>
          {/* Summary cards */}
          <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <div className="panel">
              <p className="eyebrow">Cases</p>
              <h3>{report.summary.passed_cases}/{report.summary.total_cases}</h3>
            </div>
            <div className="panel">
              <p className="eyebrow">Extraction</p>
              <h3>{(report.summary.extraction_score * 100).toFixed(0)}%</h3>
            </div>
            <div className="panel">
              <p className="eyebrow">Redaction safety</p>
              <h3>{(report.summary.redaction_safety * 100).toFixed(0)}%</h3>
            </div>
            <div className="panel">
              <p className="eyebrow">Overall</p>
              <h3>{(report.summary.overall_score * 100).toFixed(0)}%</h3>
            </div>
          </section>

          {/* Per-field accuracy */}
          <section className="panel">
            <h3>Per-field accuracy</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Accuracy</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(report.summary.field_accuracy).map(([field, acc]) => (
                  <tr key={field}>
                    <td>{field}</td>
                    <td>{(acc * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* Scorer metrics (WER, draft, latency) */}
          {report.summary.scorer_metrics ? (
            <section className="panel">
              <h3>Scorer metrics</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.summary.scorer_metrics).map(([metric, val]) => (
                    <tr key={metric}>
                      <td>{metric.replace(/_/g, " ")}</td>
                      <td>
                        {typeof val === "number" ? val.toFixed(3) : String(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}

          {/* Case-by-case breakdown */}
          <section className="panel">
            <h3>Case details ({report.cases.length} cases)</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Passed</th>
                  <th>Failures</th>
                </tr>
              </thead>
              <tbody>
                {report.cases.map((c) => (
                  <tr key={c.id}>
                    <td style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>
                      {c.id}
                    </td>
                    <td>{c.passed ? "PASS" : "FAIL"}</td>
                    <td>
                      {Object.keys(c.field_failures).length > 0
                        ? Object.keys(c.field_failures).join(", ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </>
  );
}

"use client";

import { useEffect, useState } from "react";
import { getEvalComparison } from "../../lib/api";

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

function SummaryCards({ report, label }: { report: EvalReport; label: string }) {
  const s = report.summary;
  return (
    <>
      <h3 style={{ textAlign: "center", marginBottom: 12 }}>{label}</h3>
      <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
        <div className="panel">
          <p className="eyebrow">Cases</p>
          <h3>{s.passed_cases}/{s.total_cases}</h3>
        </div>
        <div className="panel">
          <p className="eyebrow">Extraction</p>
          <h3>{(s.extraction_score * 100).toFixed(0)}%</h3>
        </div>
        <div className="panel">
          <p className="eyebrow">Redaction</p>
          <h3>{(s.redaction_safety * 100).toFixed(0)}%</h3>
        </div>
        <div className="panel">
          <p className="eyebrow">Overall</p>
          <h3>{(s.overall_score * 100).toFixed(0)}%</h3>
        </div>
      </section>
    </>
  );
}

function FieldAccuracyTable({ report }: { report: EvalReport }) {
  return (
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
  );
}

function CaseTable({ report }: { report: EvalReport }) {
  return (
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
  );
}

export default function EvalsPage() {
  const [localReport, setLocalReport] = useState<EvalReport | null>(null);
  const [sarvamReport, setSarvamReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getEvalComparison()
      .then((data) => {
        setLocalReport(data.local as unknown as EvalReport);
        setSarvamReport(data.sarvam as unknown as EvalReport);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const hasLocal = !!localReport;
  const hasSarvam = !!sarvamReport;

  return (
    <>
      <section className="panel">
        <h2>Pipeline evaluation</h2>
        <p className="muted">
          Extraction, redaction, and clustering quality measured against 53
          multilingual fixtures via <code>bhasha-test</code>. Run locally or
          with Sarvam-M for comparison.
        </p>
      </section>

      {loading ? <p className="muted">Loading eval reports…</p> : null}

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
            <p>Could not load eval reports: {error}</p>
          )}
        </div>
      ) : null}

      {!loading && !error && (hasLocal || hasSarvam) ? (
        <>
          {/* Side-by-side summary cards */}
          <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            {hasLocal ? (
              <div>
                <SummaryCards report={localReport!} label="Local (regex)" />
              </div>
            ) : (
              <div className="panel">
                <p className="muted">No local report yet.</p>
              </div>
            )}
            {hasSarvam ? (
              <div>
                <SummaryCards report={sarvamReport!} label="Sarvam-M (LLM)" />
              </div>
            ) : (
              <div className="panel">
                <p className="muted">
                  No Sarvam report yet. Run{" "}
                  <code>bhasha-test evaluate … --provider sarvam</code>
                </p>
              </div>
            )}
          </section>

          {/* Side-by-side field accuracy */}
          <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginTop: 24 }}>
            {hasLocal && <FieldAccuracyTable report={localReport!} />}
            {hasSarvam && <FieldAccuracyTable report={sarvamReport!} />}
          </section>

          {/* Scorer metrics (latency) — only for targeted runs */}
          {(localReport?.summary.scorer_metrics || sarvamReport?.summary.scorer_metrics) ? (
            <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginTop: 24 }}>
              {localReport?.summary.scorer_metrics ? (
                <section className="panel">
                  <h3>Scorer metrics — Local</h3>
                  <table className="data-table">
                    <thead>
                      <tr><th>Metric</th><th>Value</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(localReport.summary.scorer_metrics).map(([m, v]) => (
                        <tr key={m}>
                          <td>{m.replace(/_/g, " ")}</td>
                          <td>{typeof v === "number" ? v.toFixed(3) : String(v)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              ) : null}
              {sarvamReport?.summary.scorer_metrics ? (
                <section className="panel">
                  <h3>Scorer metrics — Sarvam</h3>
                  <table className="data-table">
                    <thead>
                      <tr><th>Metric</th><th>Value</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(sarvamReport.summary.scorer_metrics).map(([m, v]) => (
                        <tr key={m}>
                          <td>{m.replace(/_/g, " ")}</td>
                          <td>{typeof v === "number" ? v.toFixed(3) : String(v)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              ) : null}
            </section>
          ) : null}

          {/* Case breakdown — full width */}
          <section style={{ marginTop: 24 }}>
            {hasLocal && <CaseTable report={localReport!} />}
          </section>
        </>
      ) : null}
    </>
  );
}

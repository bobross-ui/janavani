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
      <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
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

function CaseTable({ report, label }: { report: EvalReport; label: string }) {
  return (
    <section className="panel">
      <h3>{label} ({report.cases.length} cases)</h3>
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

function ScorerMetrics({ report, label }: { report: EvalReport; label: string }) {
  const metrics = report.summary.scorer_metrics;
  if (!metrics) return null;
  return (
    <section className="panel">
      <h3>Scorer metrics — {label}</h3>
      <table className="data-table">
        <thead>
          <tr><th>Metric</th><th>Value</th></tr>
        </thead>
        <tbody>
          {Object.entries(metrics).map(([m, v]) => (
            <tr key={m}>
              <td>{m.replace(/_/g, " ")}</td>
              <td>{typeof v === "number" ? v.toFixed(3) : String(v)}</td>
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
  const hasNone = !loading && !error && !hasLocal && !hasSarvam;
  const report = localReport || sarvamReport;

  return (
    <>
      <section className="panel">
        <h2>Pipeline evaluation</h2>
        <p className="muted">
          Extraction, redaction, and clustering quality measured against
          multilingual fixtures via <code>bhasha-test</code>. Run locally or
          with Sarvam-M for comparison.
        </p>
      </section>

      {loading ? <p className="muted">Loading eval reports…</p> : null}

      {error ? (
        <div className="error">
          <p>Could not load eval reports: {error}</p>
        </div>
      ) : null}

      {hasNone ? (
        <div className="error">
          <p>No eval reports found.</p>
          <p>
            Run{" "}
            <code>
              bhasha-test evaluate data/eval_cases/grievance_cases.yaml
              --target http://localhost:8000
              --output data/eval_reports/latest.json
            </code>{" "}
            and{" "}
            <code>
              bhasha-test evaluate ... --provider sarvam
              --output data/eval_reports/sarvam.json
            </code>
          </p>
        </div>
      ) : null}

      {!loading && !error && (hasLocal || hasSarvam) ? (
        <>
          {/* Side-by-side summary cards */}
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24 }}>
            {hasLocal ? (
              <SummaryCards report={localReport!} label="Local (regex)" />
            ) : (
              <div className="panel">
                <p className="muted">No local report yet.</p>
              </div>
            )}
            {hasSarvam ? (
              <SummaryCards report={sarvamReport!} label="Sarvam-M (LLM)" />
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
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24, marginTop: 24 }}>
            {hasLocal && <FieldAccuracyTable report={localReport!} />}
            {hasSarvam && <FieldAccuracyTable report={sarvamReport!} />}
          </section>

          {/* Scorer metrics (latency) */}
          {(localReport?.summary.scorer_metrics || sarvamReport?.summary.scorer_metrics) ? (
            <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24, marginTop: 24 }}>
              {hasLocal && <ScorerMetrics report={localReport!} label="Local" />}
              {hasSarvam && <ScorerMetrics report={sarvamReport!} label="Sarvam" />}
            </section>
          ) : null}

          {/* Case breakdown — side-by-side */}
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: 24, marginTop: 24 }}>
            {hasLocal && <CaseTable report={localReport!} label="Local cases" />}
            {hasSarvam && <CaseTable report={sarvamReport!} label="Sarvam cases" />}
          </section>
        </>
      ) : null}
    </>
  );
}

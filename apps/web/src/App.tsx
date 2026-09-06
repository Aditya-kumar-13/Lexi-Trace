import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Memory = {
  id: string;
  canonical_form: string;
  state: string;
  scope_mode: string;
  evidence_confidence: number;
  positive_context: string[];
  negative_context: string[];
  variants: { surface_form: string; metaphone_key: string }[];
};

type Candidate = {
  memory_id: string;
  canonical_form: string;
  input_span: string;
  output_span: string;
  score: number;
  action: string;
  reason_codes: string[];
  features: Record<string, string | number | boolean>;
};

type Inference = {
  trace_id: string;
  formatted_text: string;
  memory_aware_text: string;
  action: string;
  total_latency_ms: number;
  changes: Candidate[];
  candidates: Candidate[];
};

type MemoryVersion = {
  id: string;
  version_number: number;
  action: string;
  reason: string;
  actor: string;
  snapshot: Record<string, unknown>;
  created_at: string;
};

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [canonical, setCanonical] = useState("Kivi");
  const [variant, setVariant] = useState("Kiwi");
  const [scope, setScope] = useState<"global" | "contextual">("contextual");
  const [positive, setPositive] = useState("Sarvam, service");
  const [negative, setNegative] = useState("fruit, food, shopping");
  const [formatted, setFormatted] = useState("Review the Sarvam Kiwi service.");
  const [result, setResult] = useState<Inference | null>(null);
  const [history, setHistory] = useState<MemoryVersion[]>([]);
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refreshMemories = useCallback(async () => {
    setMemories(await jsonRequest<Memory[]>("/api/v1/memories"));
  }, []);

  useEffect(() => {
    refreshMemories().catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : "Unable to load memories"),
    );
  }, [refreshMemories]);

  const strongestCandidate = useMemo(
    () => result?.candidates.slice().sort((a, b) => b.score - a.score)[0],
    [result],
  );

  async function teach(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await jsonRequest("/api/v1/observations/explicit", {
        method: "POST",
        body: JSON.stringify({
          canonical_form: canonical,
          variants: [variant],
          scope_mode: scope,
          positive_context: positive.split(",").map((item) => item.trim()).filter(Boolean),
          negative_context: negative.split(",").map((item) => item.trim()).filter(Boolean),
        }),
      });
      await refreshMemories();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to teach memory");
    } finally {
      setBusy(false);
    }
  }

  async function runInference(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setFeedbackMessage("");
      setResult(
        await jsonRequest<Inference>("/api/v1/infer", {
          method: "POST",
          body: JSON.stringify({ formatted_text: formatted }),
        }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to run inference");
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(verdict: "correct" | "incorrect") {
    if (!result) return;
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`/api/v1/decisions/${result.trace_id}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          verdict,
          corrected_text: verdict === "incorrect" ? result.formatted_text : null,
        }),
      });
      setFeedbackMessage(
        verdict === "correct"
          ? "Recorded as supporting evidence."
          : "Intervention rejected; affected memory was demoted for review.",
      );
      await refreshMemories();
      if (selectedMemoryId) await loadHistory(selectedMemoryId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to record feedback");
    } finally {
      setBusy(false);
    }
  }

  async function loadHistory(memoryId: string) {
    setBusy(true);
    setError("");
    try {
      setSelectedMemoryId(memoryId);
      setHistory(
        await jsonRequest<MemoryVersion[]>(`/api/v1/memories/${memoryId}/history`),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load memory history");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (!window.confirm("Reset all demo-user memories and traces?")) return;
    setBusy(true);
    setError("");
    try {
      await jsonRequest("/api/v1/reset", { method: "POST" });
      setResult(null);
      setHistory([]);
      setSelectedMemoryId(null);
      setFeedbackMessage("");
      await refreshMemories();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reset state");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header>
        <a className="brand" href="#top" aria-label="LexiTrace home">
          <span className="brand-mark">L</span>
          <span>LexiTrace</span>
        </a>
        <div className="header-copy">
          <span className="eyebrow">PERSONAL WORD MEMORY</span>
          <strong>Trust what changes.</strong>
        </div>
        <button className="secondary" onClick={reset} disabled={busy}>Reset demo</button>
      </header>

      <main id="top">
        <section className="hero">
          <div>
            <p className="eyebrow">A LOCAL, INSPECTABLE PROTOTYPE</p>
            <h1>Kivi remembers your words—without guessing.</h1>
          </div>
          <p className="hero-note">
            Teach a personal spelling, try it in context, and inspect why memory did or did not
            intervene.
          </p>
        </section>

        {error && <div className="error" role="alert">{error}</div>}

        <section className="workspace-grid">
          <form className="panel teach-panel" onSubmit={teach}>
            <div className="panel-heading">
              <span className="step">01</span>
              <div><p className="eyebrow">TEACH</p><h2>Create a trusted memory</h2></div>
            </div>
            <label>What Kivi should write<input value={canonical} onChange={(e) => setCanonical(e.target.value)} /></label>
            <label>What it may hear<input value={variant} onChange={(e) => setVariant(e.target.value)} /></label>
            <div className="two-column">
              <label>Scope<select value={scope} onChange={(e) => setScope(e.target.value as "global" | "contextual")}><option value="global">Global</option><option value="contextual">Contextual</option></select></label>
              <label>Positive context<input value={positive} onChange={(e) => setPositive(e.target.value)} disabled={scope === "global"} /></label>
            </div>
            <label>Never apply around<input value={negative} onChange={(e) => setNegative(e.target.value)} placeholder="fruit, shopping" /></label>
            <button type="submit" disabled={busy}>Teach this word <span>→</span></button>
          </form>

          <form className="panel try-panel" onSubmit={runInference}>
            <div className="panel-heading">
              <span className="step">02</span>
              <div><p className="eyebrow">TRY</p><h2>Run memory-aware text</h2></div>
            </div>
            <label>Formatted transcript<textarea value={formatted} onChange={(e) => setFormatted(e.target.value)} rows={5} /></label>
            <div className="sample-row">
              <button type="button" className="chip" onClick={() => setFormatted("Review the Sarvam Kiwi service.")}>Work context</button>
              <button type="button" className="chip" onClick={() => setFormatted("Buy kiwi fruit from the shop.")}>Fruit context</button>
            </div>
            <button type="submit" disabled={busy}>Run decision <span>→</span></button>
            <div className={`result ${result ? "visible" : ""}`}>
              <div className="result-meta">
                <span className={`badge ${result?.action ?? "idle"}`}>{result?.action ?? "waiting"}</span>
                {result && <span>{result.total_latency_ms.toFixed(2)} ms</span>}
              </div>
              <p>{result?.memory_aware_text ?? "The memory-aware result will appear here."}</p>
              {result?.action === "apply" && (
                <div className="feedback-row">
                  <span>Was this intervention right?</span>
                  <button type="button" onClick={() => sendFeedback("correct")} disabled={busy}>Correct</button>
                  <button type="button" onClick={() => sendFeedback("incorrect")} disabled={busy}>Wrong</button>
                </div>
              )}
              {feedbackMessage && <small className="feedback-message">{feedbackMessage}</small>}
            </div>
          </form>
        </section>

        <section className="inspector-grid">
          <div className="panel library">
            <div className="panel-heading compact"><span className="step">03</span><div><p className="eyebrow">MEMORY</p><h2>What LexiTrace knows</h2></div></div>
            {memories.length === 0 ? <p className="empty">No memories yet. Teach the first word above.</p> : memories.map((memory) => (
              <article className="memory-card" key={memory.id}>
                <div><strong>{memory.canonical_form}</strong><span>{memory.variants.map((item) => item.surface_form).join(", ")} → {memory.canonical_form}</span></div>
                <div className="memory-meta"><span>{memory.state}</span><span>{memory.scope_mode}</span><span>{Math.round(memory.evidence_confidence * 100)}% evidence</span></div>
                <button type="button" className="history-button" onClick={() => loadHistory(memory.id)}>View history</button>
              </article>
            ))}
            {selectedMemoryId && (
              <div className="history-list">
                <p className="eyebrow">VERSION HISTORY</p>
                {history.map((version) => (
                  <div className="history-item" key={version.id}>
                    <span>v{version.version_number}</span>
                    <div><strong>{version.action.replaceAll("_", " ")}</strong><small>{version.reason}</small></div>
                    <time>{new Date(version.created_at).toLocaleString()}</time>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel trace-panel">
            <div className="panel-heading compact"><span className="step">04</span><div><p className="eyebrow">DECISION TRACE</p><h2>Why it acted</h2></div></div>
            {!strongestCandidate ? <p className="empty">Run a decision to inspect candidates, reasons, and scores.</p> : (
              <div className="trace-content">
                <div className="score-line"><span>Confidence</span><strong>{(strongestCandidate.score * 100).toFixed(1)}%</strong></div>
                <div className="score-track"><span style={{ width: `${strongestCandidate.score * 100}%` }} /></div>
                <div className="reason-list">{strongestCandidate.reason_codes.map((reason: string) => <span key={reason}>{reason.replaceAll("_", " ")}</span>)}</div>
                <dl>{Object.entries(strongestCandidate.features).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>)}</dl>
                <small>Trace {result?.trace_id}</small>
              </div>
            )}
          </div>
        </section>
      </main>

      <footer><span>LexiTrace 0.2.0</span><span>Local-first · No model key required</span></footer>
    </div>
  );
}

export default App;

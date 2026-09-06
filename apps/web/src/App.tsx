import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Memory = {
  id: string;
  canonical_form: string;
  state: string;
  scope_mode: string;
  trust_profile: {
    posterior_mean: number;
    positive_events: number;
    negative_events: number;
    distinct_contexts: number;
    reason_code: string;
  };
  positive_context: string[];
  negative_context: string[];
  context_evidence_count: number;
  context_profile: {
    positive: { feature: string; weight: number }[];
    negative: { feature: string; weight: number }[];
  };
  semantic_evidence_count: number;
  semantic_profile: { models: Record<string, Record<string, number>> };
  asr_evidence_count: number;
  asr_profile: {
    minimum_outcomes: number;
    groups: { provider: string; model: string; state: string; observations: number }[];
  };
  variants: { surface_form: string; metaphone_key: string }[];
};

type Candidate = {
  memory_id: string;
  canonical_form: string;
  input_span: string;
  output_span: string;
  start: number;
  end: number;
  score: number;
  action: string;
  reason_codes: string[];
  blockers: string[];
  features: Record<string, string | number | boolean>;
  counterfactual: {
    reason_code: string;
    apply_threshold: number;
    score_gap_to_apply: number;
    blocking_conditions: string[];
    minimum_change: string;
  };
};

type Inference = {
  trace_id: string;
  formatted_text: string;
  memory_aware_text: string;
  action: string;
  total_latency_ms: number;
  changes: Candidate[];
  candidates: Candidate[];
  policy_version: string;
  semantic: { enabled: boolean; model: string; state: string; error?: string | null };
  counterfactual: {
    reason_code: string;
    apply_threshold?: number;
    score_gap_to_apply?: number;
    minimum_change: string;
  };
  shadow: {
    policy_id: string;
    action: string;
    memory_aware_text: string;
    action_changed: boolean;
    output_changed: boolean;
  } | null;
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
  const [example, setExample] = useState("Review the Kiwi service dashboard.");
  const [observedText, setObservedText] = useState("Message Aditya today.");
  const [acceptedText, setAcceptedText] = useState("Message Aaditya today.");
  const [observationMessage, setObservationMessage] = useState("");
  const [formatted, setFormatted] = useState("Inspect the Kiwi platform deployment.");
  const [asrAlternative, setAsrAlternative] = useState("");
  const [asrConfidence, setAsrConfidence] = useState("0.95");
  const [asrProvider, setAsrProvider] = useState("demo-asr");
  const [asrModel, setAsrModel] = useState("voice-2");
  const [shadowEnabled, setShadowEnabled] = useState(true);
  const [shadowThreshold, setShadowThreshold] = useState("0.90");
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
          positive_context: [],
          negative_context: [],
          formatted_text: scope === "contextual" ? example : "",
          accepted_text:
            scope === "contextual" ? example.split(variant).join(canonical) : "",
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
          body: JSON.stringify({
            formatted_text: formatted,
            asr: {
              provider: asrProvider,
              model: asrModel,
              confidence: Number(asrConfidence),
            },
            alternatives: asrAlternative.trim()
              ? [{
                  text: asrAlternative,
                  confidence: Number(asrConfidence),
                  provider: asrProvider,
                  model: asrModel,
                  rank: 1,
                }]
              : [],
            shadow_policy: shadowEnabled
              ? {
                  policy_id: "calibration-candidate-090",
                  apply_threshold: Number(shadowThreshold),
                }
              : null,
          }),
        }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to run inference");
    } finally {
      setBusy(false);
    }
  }

  async function observeCorrection(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await jsonRequest<{
        created_memory_ids: string[];
        trust_profiles: Record<string, { positive_events: number; distinct_contexts: number }>;
      }>("/api/v1/observations/correction", {
        method: "POST",
        body: JSON.stringify({
          event_id: crypto.randomUUID(),
          formatted_text: observedText,
          accepted_text: acceptedText,
        }),
      });
      const memoryId = response.created_memory_ids[0];
      if (!memoryId) {
        setObservationMessage("No supported word-level replacement was found.");
        return;
      }
      const trust = response.trust_profiles[memoryId];
      setObservationMessage(
        `Stored event: ${trust.positive_events} positive observations across ${trust.distinct_contexts} contexts.`,
      );
      await refreshMemories();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to observe correction");
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(verdict: "correct" | "incorrect") {
    if (!result) return;
    const target = result.action === "apply" ? result.changes[0] : strongestCandidate;
    if (!target) return;
    setBusy(true);
    setError("");
    try {
      await jsonRequest(`/api/v1/decisions/${result.trace_id}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          verdict,
          corrected_text: verdict === "incorrect" ? result.formatted_text : null,
          candidate_memory_id: target.memory_id,
          candidate_start: target.start,
        }),
      });
      setFeedbackMessage(
        verdict === "correct"
          ? "Recorded as linked evidence; repeated ASR outcomes may activate a learned route."
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
            <div className="two-column">
              <label>Scope<select value={scope} onChange={(e) => setScope(e.target.value as "global" | "contextual")}><option value="global">Global</option><option value="contextual">Learn from context</option></select></label>
              <label>Observed form<input value={variant} onChange={(e) => setVariant(e.target.value)} /></label>
            </div>
            <label>
              Example where this correction is right
              <input value={example} onChange={(e) => setExample(e.target.value)} disabled={scope === "global"} />
            </label>
            <small>LexiTrace extracts evidence from this example. It does not turn words into hand-written rules.</small>
            <button type="submit" disabled={busy}>Teach this word <span>→</span></button>
          </form>

          <form className="panel try-panel" onSubmit={runInference}>
            <div className="panel-heading">
              <span className="step">02</span>
              <div><p className="eyebrow">TRY</p><h2>Run memory-aware text</h2></div>
            </div>
            <label>Formatted transcript<textarea value={formatted} onChange={(e) => setFormatted(e.target.value)} rows={5} /></label>
            <details>
              <summary>ASR source and optional N-best evidence</summary>
              <div className="two-column">
                <label>Provider<input value={asrProvider} onChange={(e) => setAsrProvider(e.target.value)} /></label>
                <label>Model<input value={asrModel} onChange={(e) => setAsrModel(e.target.value)} /></label>
              </div>
              <label>Alternative transcript<input value={asrAlternative} onChange={(e) => setAsrAlternative(e.target.value)} placeholder="Open the Kiwi dashboard." /></label>
              <label>ASR confidence<input type="number" min="0" max="1" step="0.01" value={asrConfidence} onChange={(e) => setAsrConfidence(e.target.value)} /></label>
            </details>
            <details>
              <summary>Shadow-policy safety check</summary>
              <div className="two-column">
                <label>Candidate apply threshold<input type="number" min="0.72" max="1" step="0.005" value={shadowThreshold} onChange={(e) => setShadowThreshold(e.target.value)} /></label>
                <label className="checkbox-label"><input type="checkbox" checked={shadowEnabled} onChange={(e) => setShadowEnabled(e.target.checked)} /> Compare without affecting output</label>
              </div>
              <small>The active decision remains authoritative. Shadow output is recorded only for comparison.</small>
            </details>
            <div className="sample-row">
              <button type="button" className="chip" onClick={() => setFormatted("Inspect the Kiwi platform deployment.")}>Semantic work context</button>
              <button type="button" className="chip" onClick={() => setFormatted("Buy kiwi fruit from the shop.")}>Fruit context</button>
            </div>
            <button type="submit" disabled={busy}>Run decision <span>→</span></button>
            <div className={`result ${result ? "visible" : ""}`}>
              <div className="result-meta">
                <span className={`badge ${result?.action ?? "idle"}`}>{result?.action ?? "waiting"}</span>
                {result && <span>{result.total_latency_ms.toFixed(2)} ms</span>}
                {result?.semantic.enabled && <span>semantic {result.semantic.state}</span>}
                {result && <span>policy {result.policy_version}</span>}
              </div>
              <p>{result?.memory_aware_text ?? "The memory-aware result will appear here."}</p>
              {result?.shadow && (
                <div className="shadow-result">
                  <strong>Shadow: {result.shadow.action}</strong>
                  <span>{result.shadow.memory_aware_text}</span>
                  <small>{result.shadow.output_changed ? "Different output—review before promotion" : "Same output as active policy"}</small>
                </div>
              )}
              {(result?.action === "apply" || result?.action === "suggest") && strongestCandidate && (
                <div className="feedback-row">
                  <span>{result.action === "suggest" ? "Is this suggestion right?" : "Was this intervention right?"}</span>
                  <button type="button" onClick={() => sendFeedback("correct")} disabled={busy}>{result.action === "suggest" ? "Accept" : "Correct"}</button>
                  <button type="button" onClick={() => sendFeedback("incorrect")} disabled={busy}>Wrong</button>
                </div>
              )}
              {feedbackMessage && <small className="feedback-message">{feedbackMessage}</small>}
            </div>
          </form>
        </section>

        <form className="panel lifecycle-panel" onSubmit={observeCorrection}>
          <div className="panel-heading compact">
            <span className="step">02B</span>
            <div><p className="eyebrow">LEARN FROM USE</p><h2>Observe an accepted correction</h2></div>
          </div>
          <div className="two-column">
            <label>Formatter produced<textarea value={observedText} onChange={(e) => setObservedText(e.target.value)} rows={3} /></label>
            <label>User accepted<textarea value={acceptedText} onChange={(e) => setAcceptedText(e.target.value)} rows={3} /></label>
          </div>
          <small>Three accepted events across at least two contexts can confirm a candidate automatically. Replayed event IDs do not increase trust.</small>
          <button type="submit" disabled={busy}>Record ordinary-use evidence <span>→</span></button>
          {observationMessage && <small className="feedback-message">{observationMessage}</small>}
        </form>

        <section className="inspector-grid">
          <div className="panel library">
            <div className="panel-heading compact"><span className="step">03</span><div><p className="eyebrow">MEMORY</p><h2>What LexiTrace knows</h2></div></div>
            {memories.length === 0 ? <p className="empty">No memories yet. Teach the first word above.</p> : memories.map((memory) => (
              <article className="memory-card" key={memory.id}>
                <div><strong>{memory.canonical_form}</strong><span>{memory.variants.map((item) => item.surface_form).join(", ")} → {memory.canonical_form}</span></div>
                <div className="memory-meta"><span>{memory.state}</span><span>{memory.scope_mode}</span><span>{Math.round(memory.trust_profile.posterior_mean * 100)}% posterior trust</span></div>
                <small>{memory.trust_profile.positive_events} positive · {memory.trust_profile.negative_events} negative · {memory.trust_profile.distinct_contexts} contexts</small>
                <small>{memory.trust_profile.reason_code.replaceAll("_", " ").toLowerCase()}</small>
                <small>{memory.context_evidence_count} learned context signals</small>
                <small>{memory.semantic_evidence_count} semantic observations</small>
                <small>{memory.asr_evidence_count} provider-linked ASR outcomes</small>
                {memory.asr_profile.groups.slice(0, 1).map((group) => (
                  <small key={`${group.provider}-${group.model}`}>
                    {group.provider}/{group.model}: {group.observations}/{memory.asr_profile.minimum_outcomes} · {group.state}
                  </small>
                ))}
                {memory.context_profile.positive.length > 0 && (
                  <div className="reason-list">
                    {memory.context_profile.positive.slice(0, 4).map((item) => (
                      <span key={item.feature}>{item.feature.replace(/^(token|bigram):/, "")}</span>
                    ))}
                  </div>
                )}
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
                <div className="score-line"><span>Decision score</span><strong>{(strongestCandidate.score * 100).toFixed(1)}%</strong></div>
                <div className="score-track"><span style={{ width: `${strongestCandidate.score * 100}%` }} /></div>
                {strongestCandidate.blockers.length > 0 && (
                  <div className="reason-list">{strongestCandidate.blockers.map((blocker) => <span key={blocker}>{blocker.replaceAll("_", " ")}</span>)}</div>
                )}
                <div className="reason-list">{strongestCandidate.reason_codes.map((reason: string) => <span key={reason}>{reason.replaceAll("_", " ")}</span>)}</div>
                {result && (
                  <div className="counterfactual-box">
                    <strong>{result.counterfactual.reason_code.replaceAll("_", " ")}</strong>
                    <span>{result.counterfactual.minimum_change}</span>
                  </div>
                )}
                <dl>{Object.entries(strongestCandidate.features).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>)}</dl>
                <small>Trace {result?.trace_id}</small>
              </div>
            )}
          </div>
        </section>
      </main>

      <footer><span>LexiTrace 0.9.0</span><span>Calibrated decisions · Shadow-policy safety</span></footer>
    </div>
  );
}

export default App;

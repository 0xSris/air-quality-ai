import axios from "axios";
import { KeyboardEvent, useEffect, useMemo, useState } from "react";
import {
  exportResearchReport,
  fetchMe,
  fetchResearchSessionDetail,
  runResearchQuery,
  setApiToken,
  signIn,
  signOut,
} from "../services/api";
import { AgentStep, DashboardContext, ResearchReport, SessionDetail, UserProfile } from "../types/research";

type AgentDockProps = {
  siteId: number;
  networkScope: "india" | "global";
  modelName: string;
  profileFocus: "zip_only" | "external_augmented";
  pollutantFocus: "both" | "o3" | "no2";
  horizonHours: number;
  selectedCityLabel: string | null;
  dashboardContext: DashboardContext;
  externalRunRequest: { nonce: number; query: string } | null;
  onAdoptQuery: (query: string) => void;
  onInvestigationUpdate?: (state: {
    busy: boolean;
    report: ResearchReport | null;
    error: string | null;
    query: string;
  }) => void;
};

const RUN_BLUEPRINT = [
  "Searching station history...",
  "Reading live O3 / NO2 feed...",
  "Comparing forecast profile...",
  "Checking threshold rules...",
  "Ranking risk windows...",
  "Generating brief...",
];

function formatApiError(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}

function formatTime(value: string | undefined | null) {
  if (!value) return "--:--:--";
  return new Date(value).toLocaleTimeString();
}

function stepStatusClass(status: AgentStep["status"]) {
  switch (status) {
    case "running":
      return "running";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    case "partial":
      return "partial";
    default:
      return "queued";
  }
}

function stripAgentContext(value: string) {
  return value.split("\n\nContext:")[0].trim();
}

export function AgentDock({
  siteId,
  networkScope,
  modelName,
  profileFocus,
  pollutantFocus,
  horizonHours,
  selectedCityLabel,
  dashboardContext,
  externalRunRequest,
  onAdoptQuery,
  onInvestigationUpdate,
}: AgentDockProps) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("aqai-auth-token"));
  const [user, setUser] = useState<UserProfile | null>(null);
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [authForm, setAuthForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [confidenceOpen, setConfidenceOpen] = useState(false);
  const [runPhaseIndex, setRunPhaseIndex] = useState(0);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  useEffect(() => {
    setApiToken(token);
    if (token) {
      localStorage.setItem("aqai-auth-token", token);
    } else {
      localStorage.removeItem("aqai-auth-token");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let active = true;

    async function load() {
      try {
        const me = await fetchMe();
        if (!active) return;
        setUser(me);
      } catch {
        if (!active) return;
        setToken(null);
        setUser(null);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (!busy) return;
    const interval = window.setInterval(() => {
      setRunPhaseIndex((current) => Math.min(current + 1, RUN_BLUEPRINT.length - 1));
    }, 650);
    return () => window.clearInterval(interval);
  }, [busy]);

  useEffect(() => {
    if (!externalRunRequest) return;
    setQuery(externalRunRequest.query);
    if (!user) return;
    void handleRunQuery(externalRunRequest.query);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalRunRequest?.nonce, user]);

  async function handleSignIn() {
    setError(null);
    try {
      const response = await signIn(authForm);
      setToken(response.token);
      setUser(response.user);
      setAuthForm({ email: "", password: "" });
    } catch (authError) {
      setError(formatApiError(authError, "Unable to sign in to the investigation agent."));
    }
  }

  async function handleSignOut() {
    setError(null);
    try {
      await signOut();
    } catch {
      // Local session cleanup should still happen if the API request is interrupted.
    } finally {
      setToken(null);
      setUser(null);
      setSessionDetail(null);
      setQuery("");
    }
  }

  async function handleRunQuery(overrideQuery?: string) {
    const nextQuery = (overrideQuery ?? query).trim();
    if (!nextQuery) return;
    setBusy(true);
    setError(null);
    setRunPhaseIndex(0);
    try {
      const response = await runResearchQuery({
        session_id: sessionDetail?.session.session_id,
        query: nextQuery,
        mode: "environment",
        depth: "standard",
        site_id: siteId,
        network_scope: networkScope,
        dashboard_context: dashboardContext,
      });
      const detail = await fetchResearchSessionDetail(response.session.session_id);
      setSessionDetail(detail);
      setQuery(nextQuery);
      onAdoptQuery(stripAgentContext(nextQuery));
    } catch (runError) {
      setError(formatApiError(runError, "The investigation agent could not complete this run."));
    } finally {
      setBusy(false);
    }
  }

  async function handleExportMarkdown() {
    const report = sessionDetail?.reports?.[0];
    const session = sessionDetail?.session;
    if (!report || !session) return;
    try {
      const exported = await exportResearchReport(session.session_id, report.report_id, "markdown");
      window.open(`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}${exported.download_url}`, "_blank");
    } catch (exportError) {
      setError(formatApiError(exportError, "Unable to export this brief right now."));
    }
  }

  async function handleCopyBrief() {
    const report = sessionDetail?.reports?.[0];
    if (!report) return;
    try {
      await navigator.clipboard.writeText(report.summary_markdown);
    } catch {
      setError("Copy failed. Your browser blocked clipboard access.");
    }
  }

  function handleAuthKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void handleSignIn();
    }
  }

  const latestReport = sessionDetail?.reports?.[0] ?? null;
  const sourceList = latestReport?.sources.slice(0, 6) ?? [];
  const traceSteps = sessionDetail?.steps ?? [];

  const liveRunSteps = useMemo(() => {
    if (!busy) return [];
    return RUN_BLUEPRINT.map((step, index) => ({
      step_id: `live-${step}`,
      name: step,
      status: index < runPhaseIndex ? "completed" : index === runPhaseIndex ? "running" : "pending",
      summary: index === runPhaseIndex ? "in progress" : index < runPhaseIndex ? "finished" : "queued",
      started_at: new Date().toISOString(),
      finished_at: index < runPhaseIndex ? new Date().toISOString() : null,
    })) as AgentStep[];
  }, [busy, runPhaseIndex]);

  const displayedSteps = busy ? liveRunSteps : traceSteps;
  const confidence = latestReport?.confidence ?? null;
  const latestMessage = sessionDetail?.messages[sessionDetail.messages.length - 1];

  useEffect(() => {
    onInvestigationUpdate?.({
      busy,
      report: latestReport,
      error,
      query,
    });
  }, [busy, latestReport, error, query, onInvestigationUpdate]);

  return (
    <section className="agent-terminal">
      <div className="agent-terminal-topline">
        <div>
          <div className="mono-label">Investigation terminal</div>
          <h4>Agent audit trace and environmental brief.</h4>
        </div>
        <div className="terminal-meta">
          <span>{user ? `${user.display_name} online` : "sign in required"}</span>
          <span>{selectedCityLabel ?? "no city selected"}</span>
          <span>{modelName.split("_").join(" ")}</span>
          {user ? (
            <button type="button" className="terminal-logout" onClick={() => void handleSignOut()}>
              Sign out
            </button>
          ) : null}
        </div>
      </div>

      {!user ? (
        <div className="terminal-auth">
          <input
            className="terminal-input compact"
            placeholder="email"
            value={authForm.email}
            onChange={(event) => setAuthForm((state) => ({ ...state, email: event.target.value }))}
            onKeyDown={handleAuthKeyDown}
          />
          <input
            className="terminal-input compact"
            type="password"
            placeholder="password"
            value={authForm.password}
            onChange={(event) => setAuthForm((state) => ({ ...state, password: event.target.value }))}
            onKeyDown={handleAuthKeyDown}
          />
          <button className="terminal-run" type="button" onClick={() => void handleSignIn()}>
            Connect agent
          </button>
        </div>
      ) : (
        <>
          <div className="terminal-context-row">
            <span>station Site {siteId}</span>
            <span>scope {networkScope}</span>
            <span>pollutant {pollutantFocus}</span>
            <span>window {horizonHours}h</span>
            <span>profile {profileFocus}</span>
            <span>{busy ? "investigating" : "ready"}</span>
          </div>
          {query ? <div className="terminal-active-query">{query.split("\n")[0]}</div> : null}
          <div className="terminal-command-row docked-command">
            <div className="terminal-command-shell">
              <span>&gt;</span>
              <input
                className="terminal-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    void handleRunQuery();
                  }
                }}
                placeholder="Ask a follow-up, request a causal chain, compare models, or simulate a scenario..."
              />
            </div>
            <button className="terminal-run" type="button" onClick={() => void handleRunQuery()}>
              Run from context
            </button>
          </div>
        </>
      )}

      {error ? <div className="terminal-error">{error}</div> : null}

      <div className="terminal-grid">
        <div className="terminal-trace-column">
          <div className="terminal-section-heading">Audit trace</div>
          <div className="trace-list">
            {displayedSteps.length ? (
              displayedSteps.map((step) => (
                <button
                  key={step.step_id}
                  type="button"
                  className={selectedStepId === step.step_id ? "trace-row active" : "trace-row"}
                  onClick={() => setSelectedStepId(step.step_id)}
                >
                  <span className={`trace-status ${stepStatusClass(step.status)}`} />
                  <div className="trace-copy">
                    <div className="trace-title-row">
                      <strong>{step.name}</strong>
                      <span>{formatTime(step.finished_at ?? step.started_at)}</span>
                    </div>
                    <p>{step.summary}</p>
                    {selectedStepId === step.step_id ? (
                      <details className="raw-step-details" open>
                        <summary>raw data checked</summary>
                        <pre>{JSON.stringify(step.payload ?? { status: step.status, summary: step.summary }, null, 2)}</pre>
                        {step.status === "failed" || step.status === "partial" ? (
                          <button
                            type="button"
                            className="text-action"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleRunQuery(query);
                            }}
                          >
                            Retry from this step
                          </button>
                        ) : null}
                      </details>
                    ) : null}
                  </div>
                </button>
              ))
            ) : (
              <div className="trace-empty">No investigation has been run in this session yet.</div>
            )}
          </div>

          <div className="terminal-section-heading">Sources consulted</div>
          <div className="source-list">
            {sourceList.length ? (
              sourceList.map((source) => (
                <div key={source.source_id} className="source-row">
                  <div>
                    <strong>{source.title}</strong>
                    <span>{source.source_type}</span>
                  </div>
                  <em>{Math.round(source.credibility * 100)}%</em>
                </div>
              ))
            ) : (
              <div className="trace-empty">SIH baseline, live feed, alert thresholds, and city network sources will appear after a run.</div>
            )}
          </div>
        </div>

        <div className="terminal-brief-column">
          <div className="terminal-section-heading">Environmental intelligence brief</div>
          {latestReport ? (
            <>
              <div className="brief-header">
                <div>
                  <h5>{latestReport.title}</h5>
                  <p>{latestReport.overview}</p>
                </div>
                <div className="brief-score">
                  <span>confidence</span>
                  <strong>{Math.round(latestReport.confidence.overall * 100)}%</strong>
                </div>
              </div>

              <div className="brief-actions">
                <button type="button" className="text-action" onClick={() => void handleCopyBrief()}>
                  Copy brief
                </button>
                <button type="button" className="text-action" onClick={() => void handleExportMarkdown()}>
                  Export markdown
                </button>
                <button type="button" className="text-action" onClick={() => setConfidenceOpen((value) => !value)}>
                  {confidenceOpen ? "Hide confidence" : "Confidence breakdown"}
                </button>
              </div>

              {confidenceOpen && confidence ? (
                <div className="confidence-breakdown">
                  <div>
                    <span>overall</span>
                    <strong>{Math.round(confidence.overall * 100)}%</strong>
                  </div>
                  <div>
                    <span>data quality</span>
                    <strong>{Math.round(confidence.data_quality * 100)}%</strong>
                  </div>
                  <div>
                    <span>coverage</span>
                    <strong>{Math.round(confidence.coverage * 100)}%</strong>
                  </div>
                  <div>
                    <span>reasoning</span>
                    <strong>{Math.round(confidence.reasoning_strength * 100)}%</strong>
                  </div>
                </div>
              ) : null}

              <div className="brief-section-list">
                {latestReport.sections.map((section) => (
                  <details key={section.key} className="brief-section-row" open={section.key === latestReport.sections[0]?.key}>
                    <summary className="brief-section-head">
                      <span>{section.title}</span>
                      <em>{section.sources.join(" · ")}</em>
                    </summary>
                    <p>{section.content}</p>
                  </details>
                ))}
              </div>

              {latestReport.claims.length ? <div className="terminal-section-heading gap-top">Confidence factors</div> : null}
              {latestReport.claims.slice(0, 3).map((claim) => (
                <div key={claim.claim} className="claim-row">
                  <strong>{claim.claim}</strong>
                  <span>{Math.round(claim.confidence * 100)}%</span>
                </div>
              ))}

              {latestReport.follow_ups.length ? (
                <>
                  <div className="terminal-section-heading gap-top">Suggested next investigations</div>
                  <div className="follow-up-list">
                    {latestReport.follow_ups.map((followUp) => (
                      <button
                        key={followUp}
                        type="button"
                        className="follow-up-chip"
                        onClick={() => {
                          setQuery(followUp);
                          onAdoptQuery(followUp);
                        }}
                      >
                        {followUp}
                      </button>
                    ))}
                  </div>
                </>
              ) : null}

              {latestMessage ? (
                <div className="terminal-tail-note">
                  Last reply at {formatTime(latestMessage.created_at)} · {latestMessage.role}
                </div>
              ) : null}
            </>
          ) : (
            <div className="brief-empty">
              <p>Environmental Intelligence Brief</p>
              <span>Awaiting the next investigation run.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

import axios from "axios";
import { KeyboardEvent, useEffect, useMemo, useState } from "react";
import {
  createResearchSession,
  deleteResearchSession,
  exportResearchReport,
  fetchKnowledgeGraph,
  fetchMe,
  fetchResearchSessionDetail,
  fetchResearchSessions,
  runResearchQuery,
  setApiToken,
  signIn,
  signOut,
  signUp,
  submitResearchFeedback,
  updateResearchSession,
} from "../services/api";
import {
  AgentStep,
  AuthResponse,
  KnowledgeGraphResponse,
  ResearchMode,
  ResearchReport,
  SessionDetail,
  SessionSummary,
  UserProfile,
} from "../types/research";

type WorkspaceProps = {
  siteId: number;
  networkScope: "india" | "global";
};

type UiPrefs = {
  theme: "dark" | "light";
  focusMode: boolean;
};

const defaultPrefs: UiPrefs = {
  theme: "dark",
  focusMode: false,
};

function formatApiError(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      if (first?.msg) {
        return first.msg;
      }
    }
    if (error.response?.status === 422) {
      return "Please check the form. Passwords must be at least 8 characters, and all visible fields should be filled.";
    }
  }
  return fallback;
}

function modeLabel(mode: ResearchMode) {
  return mode === "environment" ? "Environment" : mode.charAt(0).toUpperCase() + mode.slice(1);
}

export function ResearchWorkspace({ siteId, networkScope }: WorkspaceProps) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("aqai-auth-token"));
  const [user, setUser] = useState<UserProfile | null>(null);
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [authForm, setAuthForm] = useState({ email: "", password: "", display_name: "" });
  const [authError, setAuthError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(() => localStorage.getItem("aqai-active-session"));
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ResearchMode>("environment");
  const [depth, setDepth] = useState<"quick" | "standard" | "deep">("standard");
  const [busy, setBusy] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");
  const [graph, setGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [prefs, setPrefs] = useState<UiPrefs>(() => {
    const raw = localStorage.getItem("aqai-workspace-prefs");
    return raw ? { ...defaultPrefs, ...JSON.parse(raw) } : defaultPrefs;
  });
  const [commandOpen, setCommandOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [workspaceExpanded, setWorkspaceExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"report" | "sources" | "trace" | "memory">("report");
  const [lastRunDegraded, setLastRunDegraded] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    setApiToken(token);
    if (token) {
      localStorage.setItem("aqai-auth-token", token);
    } else {
      localStorage.removeItem("aqai-auth-token");
    }
  }, [token]);

  useEffect(() => {
    localStorage.setItem("aqai-workspace-prefs", JSON.stringify(prefs));
    document.body.dataset.theme = prefs.theme;
  }, [prefs]);

  useEffect(() => {
    if (selectedSessionId) {
      localStorage.setItem("aqai-active-session", selectedSessionId);
    } else {
      localStorage.removeItem("aqai-active-session");
    }
  }, [selectedSessionId]);

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!token) return;
    void initializeWorkspace();
  }, [token]);

  useEffect(() => {
    if (!token || !selectedSessionId) return;
    void loadSession(selectedSessionId);
  }, [selectedSessionId, token]);

  async function initializeWorkspace() {
    try {
      const [me, sessionList, graphData] = await Promise.all([
        fetchMe(),
        fetchResearchSessions(),
        fetchKnowledgeGraph(),
      ]);
      setUser(me);
      setSessions(sessionList);
      setGraph(graphData);
      if (!selectedSessionId && sessionList[0]) {
        setSelectedSessionId(sessionList[0].session_id);
      }
    } catch {
      setToken(null);
      setUser(null);
    }
  }

  async function loadSession(sessionId: string) {
    const detail = await fetchResearchSessionDetail(sessionId);
    setSessionDetail(detail);
    setRunError(null);
  }

  async function handleAuth() {
    setAuthError(null);
    const trimmedEmail = authForm.email.trim();
    const trimmedDisplayName = authForm.display_name.trim();
    if (!trimmedEmail) {
      setAuthError("Enter your email to continue.");
      return;
    }
    if (!authForm.password) {
      setAuthError("Enter a password to continue.");
      return;
    }
    if (authMode === "signup" && authForm.password.length < 8) {
      setAuthError("Use a password with at least 8 characters.");
      return;
    }
    try {
      const response: AuthResponse =
        authMode === "signin"
          ? await signIn({ email: trimmedEmail, password: authForm.password })
          : await signUp({
              email: trimmedEmail,
              password: authForm.password,
              display_name: trimmedDisplayName,
            });
      setToken(response.token);
      setUser(response.user);
      setAuthForm({ email: "", password: "", display_name: "" });
    } catch (error) {
      setAuthError(formatApiError(error, "Authentication failed."));
    }
  }

  async function handleCreateSession() {
    const session = await createResearchSession({
      title: "New research session",
      mode,
      depth,
      tags: ["environment", networkScope],
    });
    const updated = await fetchResearchSessions();
    setSessions(updated);
    setSelectedSessionId(session.session_id);
  }

  async function handleRunQuery(forcedQuery?: string) {
    const nextQuery = (forcedQuery ?? query).trim();
    if (!nextQuery) return;
    setBusy(true);
    setRunError(null);
    try {
      const response = await runResearchQuery({
        session_id: selectedSessionId ?? undefined,
        query: nextQuery,
        mode,
        depth,
        site_id: siteId,
        network_scope: networkScope,
      });
      const sessionList = await fetchResearchSessions();
      const graphData = await fetchKnowledgeGraph();
      setSessions(sessionList);
      setGraph(graphData);
      setSelectedSessionId(response.session.session_id);
      setSessionDetail({
        session: response.session,
        messages: response.messages,
        reports: [response.report, ...(sessionDetail?.reports ?? [])],
        steps: response.steps,
      });
      setLastRunDegraded(response.degraded);
      setWorkspaceExpanded(true);
      setActiveTab("report");
      setExpandedSections(
        Object.fromEntries(response.report.sections.map((section) => [section.key, true])),
      );
      setQuery("");
    } catch (error) {
      setRunError(formatApiError(error, "The investigation run failed before a report could be assembled."));
    } finally {
      setBusy(false);
    }
  }

  async function handleSessionToggle(
    session: SessionSummary,
    payload: Partial<Pick<SessionSummary, "pinned" | "bookmarked" | "compare_selected">>,
  ) {
    await updateResearchSession(session.session_id, payload);
    const updated = await fetchResearchSessions();
    setSessions(updated);
    if (selectedSessionId === session.session_id) {
      await loadSession(session.session_id);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    await deleteResearchSession(sessionId);
    const updated = await fetchResearchSessions();
    setSessions(updated);
    if (selectedSessionId === sessionId) {
      setSelectedSessionId(updated[0]?.session_id ?? null);
      setSessionDetail(null);
    }
  }

  async function handleExport(format: "json" | "markdown" | "pdf") {
    if (!sessionDetail?.reports[0]) return;
    const exported = await exportResearchReport(
      sessionDetail.session.session_id,
      sessionDetail.reports[0].report_id,
      format,
    );
    window.open(`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}${exported.download_url}`, "_blank");
  }

  async function handleFeedback(targetType: "summary" | "section" | "source", targetKey: string, value: "positive" | "negative") {
    if (!sessionDetail?.reports[0]) return;
    await submitResearchFeedback({
      report_id: sessionDetail.reports[0].report_id,
      target_type: targetType,
      target_key: targetKey,
      value,
    });
  }

  const filteredSessions = useMemo(() => {
    const needle = historyFilter.trim().toLowerCase();
    if (!needle) return sessions;
    return sessions.filter(
      (session) =>
        session.title.toLowerCase().includes(needle) ||
        session.mode.toLowerCase().includes(needle) ||
        session.tags.some((tag) => tag.toLowerCase().includes(needle)),
    );
  }, [historyFilter, sessions]);

  const latestReport: ResearchReport | null = sessionDetail?.reports?.[0] ?? null;
  const followUps = latestReport?.follow_ups ?? [];
  const latestMessages = (sessionDetail?.messages ?? []).slice(-6);
  const latestSteps = (sessionDetail?.steps ?? []).slice(0, 8);
  const graphNodes = graph?.nodes.slice(0, 10) ?? [];
  const stepSummary = latestSteps.length
    ? latestSteps.map((step) => `${step.name}: ${step.status}`).join(" · ")
    : "No recent agent execution yet.";

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      void handleRunQuery();
    }
  }

  if (!token || !user) {
    return (
      <section className="panel workspace-auth">
        <div className="panel-header">
          <div>
            <h3>Research Copilot</h3>
            <p className="panel-copy">Ask a focused question and get a grounded air-quality brief with evidence, confidence, and follow-ups.</p>
          </div>
        </div>
        <div className="auth-grid">
          <div className="auth-card">
            <div className="focus-switcher">
              <button className={authMode === "signin" ? "focus-button active" : "focus-button"} onClick={() => setAuthMode("signin")}>
                Sign in
              </button>
              <button className={authMode === "signup" ? "focus-button active" : "focus-button"} onClick={() => setAuthMode("signup")}>
                Sign up
              </button>
            </div>
            <input className="workspace-input" placeholder="Email" value={authForm.email} onChange={(event) => setAuthForm((state) => ({ ...state, email: event.target.value }))} />
            {authMode === "signup" ? (
              <input className="workspace-input" placeholder="Display name (optional)" value={authForm.display_name} onChange={(event) => setAuthForm((state) => ({ ...state, display_name: event.target.value }))} />
            ) : null}
            <input className="workspace-input" type="password" placeholder="Password" value={authForm.password} onChange={(event) => setAuthForm((state) => ({ ...state, password: event.target.value }))} />
            {authError ? <div className="workspace-error">{authError}</div> : null}
            <button className="workspace-primary" onClick={() => void handleAuth()}>
              {authMode === "signin" ? "Open workspace" : "Create workspace account"}
            </button>
          </div>
          <div className="auth-sidecard">
            <div className="workspace-kicker">Pipeline</div>
            <h4>Evidence-first analysis</h4>
            <p>
              The agent combines station readings, forecast windows, live-network context, source scoring, and a saved execution trace.
            </p>
            <div className="workspace-mini-grid">
              <div className="workspace-mini-card">
                <span>Generation</span>
                <strong>llama-3.3-70b-versatile</strong>
              </div>
              <div className="workspace-mini-card">
                <span>Embeddings</span>
                <strong>all-MiniLM-L6-v2</strong>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className={prefs.focusMode ? "panel workspace-shell focus" : "panel workspace-shell"}>
      <div className="panel-header">
        <div>
          <h3>Research Copilot</h3>
          <p className="panel-copy">Focused investigations for the selected station, forecast window, and live air-quality network.</p>
        </div>
        <div className="focus-switcher">
          <button className={workspaceExpanded ? "focus-button active" : "focus-button"} onClick={() => setWorkspaceExpanded((value) => !value)}>
            {workspaceExpanded ? "Compact view" : "Open workspace"}
          </button>
          <button className="focus-button" onClick={() => setPrefs((state) => ({ ...state, focusMode: !state.focusMode }))}>
            {prefs.focusMode ? "Exit focus" : "Focus mode"}
          </button>
          <button className="focus-button" onClick={() => setPrefs((state) => ({ ...state, theme: state.theme === "dark" ? "light" : "dark" }))}>
            Theme: {prefs.theme}
          </button>
          <button className="focus-button" onClick={() => setCommandOpen(true)}>
            Command palette
          </button>
          <button className="focus-button" onClick={() => void signOut().finally(() => { setToken(null); setUser(null); })}>
            Sign out
          </button>
        </div>
      </div>

      <div className="workspace-overview">
        <div className="workspace-overview-card">
          <div className="workspace-kicker">Signed in</div>
          <strong>{user.display_name}</strong>
          <div className="workspace-meta">{user.email}</div>
        </div>
        <div className="workspace-overview-card">
          <div className="workspace-kicker">Active scope</div>
          <strong>Delhi Site {siteId}</strong>
          <div className="workspace-meta">{networkScope === "india" ? "India live network context" : "Global live network context"}</div>
        </div>
        <div className="workspace-overview-card">
          <div className="workspace-kicker">Saved sessions</div>
          <strong>{sessions.length}</strong>
          <div className="workspace-meta">{latestReport ? "Latest report ready" : "No report yet in this session"}</div>
        </div>
        <div className="workspace-overview-card">
          <div className="workspace-kicker">Trace health</div>
          <strong>{latestSteps.length ? `${latestSteps.length} recent steps` : "Standby"}</strong>
          <div className="workspace-meta">{graphNodes.length ? `${graphNodes.length} memory nodes visible` : "Knowledge graph will grow with use"}</div>
        </div>
      </div>

      <div className="workspace-sticky workspace-dock">
        <div className="workspace-command-row">
          <select value={mode} onChange={(event) => setMode(event.target.value as ResearchMode)}>
            <option value="environment">Environment</option>
            <option value="company">Company</option>
            <option value="person">Person</option>
            <option value="market">Market</option>
            <option value="job">Job / Role</option>
            <option value="product">Product</option>
          </select>
          <select value={depth} onChange={(event) => setDepth(event.target.value as "quick" | "standard" | "deep")}>
            <option value="quick">Quick</option>
            <option value="standard">Standard</option>
            <option value="deep">Deep</option>
          </select>
          <button className="ghost-button" onClick={() => void handleCreateSession()}>
            New session
          </button>
          <button className="workspace-primary" onClick={() => void handleRunQuery()} disabled={busy}>
            {busy ? "Investigating..." : "Run agent"}
          </button>
        </div>
        <textarea
          className="workspace-composer"
          placeholder="Example: Why is O3 rising at this station, and what should I watch in the next 24 hours?"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleComposerKeyDown}
        />
        <div className="workspace-composer-actions">
          <div className="panel-chips">
            <span className="panel-chip">Site {siteId}</span>
            <span className="panel-chip">{networkScope}</span>
            <span className="panel-chip">Ctrl/Cmd + Enter</span>
          </div>
          {followUps.length ? (
            <div className="followup-row">
              {followUps.slice(0, 3).map((item) => (
                <button key={item} className="focus-button" onClick={() => void handleRunQuery(item)}>
                  {item}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="workspace-runtime-strip">
        <div className={busy ? "workspace-runtime-card active" : "workspace-runtime-card"}>
          <div className="workspace-kicker">Run state</div>
          <strong>{busy ? "Investigating now" : latestReport ? "Report ready" : "Awaiting a question"}</strong>
          <p>{busy ? "Ranking evidence and assembling the brief." : stepSummary}</p>
        </div>
        <div className={lastRunDegraded ? "workspace-runtime-card warning" : "workspace-runtime-card"}>
          <div className="workspace-kicker">Synthesis path</div>
          <strong>{lastRunDegraded ? "Local fallback active" : "Primary pipeline"}</strong>
          <p>
            {lastRunDegraded
              ? "Built from local station, forecast, alert, and live-network evidence."
              : "Using structured evidence scoring with the configured synthesis path."}
          </p>
        </div>
        <div className={runError ? "workspace-runtime-card danger" : "workspace-runtime-card"}>
          <div className="workspace-kicker">Status</div>
          <strong>{runError ? "Run failed" : "System transparent"}</strong>
          <p>{runError ?? "Execution steps, confidence, and sources remain inspectable after every run."}</p>
        </div>
      </div>

      {!workspaceExpanded ? (
        <div className="workspace-collapsed-grid">
          <div className="workspace-preview-card">
            <div className="workspace-kicker">Latest report</div>
            <strong>{latestReport?.title ?? "No investigation run yet"}</strong>
            <p>
              {latestReport?.overview ??
                "Start with a question about the selected station, forecast peak, alerts, or live-network city comparison."}
            </p>
          </div>
          <div className="workspace-preview-card">
            <div className="workspace-kicker">Recent session</div>
            <strong>{sessions[0]?.title ?? "No session yet"}</strong>
            <p>{sessions[0]?.latest_query ?? "Recent investigations will appear here."}</p>
          </div>
          <div className="workspace-preview-card">
            <div className="workspace-kicker">Quick actions</div>
            <div className="followup-row">
              <button className="focus-button" onClick={() => setWorkspaceExpanded(true)}>Open full workspace</button>
              <button className="focus-button" onClick={() => void handleExport("markdown")} disabled={!latestReport}>Export brief</button>
              <button className="focus-button" onClick={() => setCommandOpen(true)}>Command palette</button>
            </div>
          </div>
        </div>
      ) : (
        <div className="workspace-layout workspace-layout-refined">
        <aside className="workspace-sidebar">
          <div className="workspace-profile">
            <div className="workspace-kicker">Session library</div>
            <div className="workspace-meta">Saved investigations and follow-up threads.</div>
          </div>
          <div className="workspace-toolbar">
            <input
              className="workspace-input"
              placeholder="Search sessions"
              value={historyFilter}
              onChange={(event) => setHistoryFilter(event.target.value)}
            />
          </div>
          <div className="workspace-session-list">
            {filteredSessions.map((session) => (
              <div
                key={session.session_id}
                className={selectedSessionId === session.session_id ? "session-item active" : "session-item"}
                onClick={() => setSelectedSessionId(session.session_id)}
              >
                <div className="session-item-head">
                  <strong>{session.title}</strong>
                  <span>{modeLabel(session.mode)}</span>
                </div>
                <div className="workspace-meta">{session.latest_query ?? "No messages yet"}</div>
                <div className="session-actions">
                  <button className="ghost-button" onClick={(event) => { event.stopPropagation(); void handleSessionToggle(session, { pinned: !session.pinned }); }}>
                    {session.pinned ? "Unpin" : "Pin"}
                  </button>
                  <button className="ghost-button" onClick={(event) => { event.stopPropagation(); void handleSessionToggle(session, { bookmarked: !session.bookmarked }); }}>
                    {session.bookmarked ? "Unsave" : "Save"}
                  </button>
                  <button className="ghost-button" onClick={(event) => { event.stopPropagation(); void handleDeleteSession(session.session_id); }}>
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <div className="workspace-report">
          <div className="workspace-tabbar">
            <button className={activeTab === "report" ? "focus-button active" : "focus-button"} onClick={() => setActiveTab("report")}>
              Report
            </button>
            <button className={activeTab === "sources" ? "focus-button active" : "focus-button"} onClick={() => setActiveTab("sources")}>
              Sources
            </button>
            <button className={activeTab === "trace" ? "focus-button active" : "focus-button"} onClick={() => setActiveTab("trace")}>
              Agent log
            </button>
            <button className={activeTab === "memory" ? "focus-button active" : "focus-button"} onClick={() => setActiveTab("memory")}>
              Memory
            </button>
            <div className="workspace-tab-actions">
              <button className="ghost-button" onClick={() => void handleExport("markdown")} disabled={!latestReport}>
                Markdown
              </button>
              <button className="ghost-button" onClick={() => void handleExport("json")} disabled={!latestReport}>
                JSON
              </button>
              <button className="ghost-button" onClick={() => void handleExport("pdf")} disabled={!latestReport}>
                PDF
              </button>
            </div>
          </div>

          {latestReport && activeTab === "report" ? (
            <div className="report-card">
              <div className="report-header">
                <div>
                  <div className="workspace-kicker">Structured report</div>
                  <h4>{latestReport.title}</h4>
                  <p>{latestReport.overview}</p>
                </div>
                <div className="report-actions">
                  <button className="ghost-button" onClick={() => void handleFeedback("summary", latestReport.report_id, "positive")}>Helpful</button>
                  <button className="ghost-button" onClick={() => void handleFeedback("summary", latestReport.report_id, "negative")}>Needs work</button>
                  <button className="ghost-button" onClick={() => navigator.clipboard.writeText(latestReport.summary_markdown)}>Copy</button>
                </div>
              </div>
              <div className="confidence-grid">
                <div className="confidence-card"><span>Overall</span><strong>{(latestReport.confidence.overall * 100).toFixed(0)}%</strong></div>
                <div className="confidence-card"><span>Data quality</span><strong>{(latestReport.confidence.data_quality * 100).toFixed(0)}%</strong></div>
                <div className="confidence-card"><span>Coverage</span><strong>{(latestReport.confidence.coverage * 100).toFixed(0)}%</strong></div>
                <div className="confidence-card"><span>Reasoning</span><strong>{(latestReport.confidence.reasoning_strength * 100).toFixed(0)}%</strong></div>
              </div>
              <div className="workspace-section-list">
                {latestReport.sections.map((section) => {
                  const open = expandedSections[section.key] ?? true;
                  return (
                    <div key={section.key} className="workspace-section">
                      <button
                        className="workspace-section-toggle"
                        onClick={() => setExpandedSections((state) => ({ ...state, [section.key]: !open }))}
                      >
                        <span>{section.title}</span>
                        <span>{open ? "Hide" : "Show"}</span>
                      </button>
                      {open ? (
                        <div className="workspace-section-body">
                          <p>{section.content}</p>
                          <div className="panel-chips">
                            {section.sources.map((source) => (
                              <span key={source} className="panel-chip">{source}</span>
                            ))}
                          </div>
                          <div className="report-actions">
                            <button className="ghost-button" onClick={() => void handleFeedback("section", section.key, "positive")}>Helpful</button>
                            <button className="ghost-button" onClick={() => void handleFeedback("section", section.key, "negative")}>Needs work</button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {latestReport && activeTab === "sources" ? (
            <div className="report-card">
              <div className="report-header">
                <div>
                  <div className="workspace-kicker">Source grounding</div>
                  <h4>Evidence and credibility</h4>
                  <p>Open sources only when you need to verify a claim, compare clusters, or inspect disagreement.</p>
                </div>
              </div>
              <div className="workspace-source-grid">
                {latestReport.sources.map((source) => (
                  <div key={source.source_id} className="source-card">
                    <div className="workspace-kicker">{source.source_type}</div>
                    <strong>{source.title}</strong>
                    <p>{source.snippet}</p>
                    <div className="panel-chips">
                      <span className="panel-chip">Credibility {(source.credibility * 100).toFixed(0)}%</span>
                      {source.cluster ? <span className="panel-chip">{source.cluster}</span> : null}
                    </div>
                    <div className="report-actions">
                      <button className="ghost-button" onClick={() => void handleFeedback("source", source.source_id, "positive")}>Useful source</button>
                      {source.url ? (
                        <button className="ghost-button" onClick={() => window.open(source.url!, "_blank")}>Open</button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === "trace" ? (
            <div className="workspace-dual-column">
              <div className="workspace-sidepanel">
                <div className="workspace-kicker">Agent timeline</div>
                <div className="agent-step-list">
                  {latestSteps.length ? latestSteps.map((step: AgentStep) => (
                    <div key={step.step_id} className={`agent-step-card ${step.status}`}>
                      <strong>{step.name}</strong>
                      <p>{step.summary}</p>
                      <span>{new Date(step.started_at).toLocaleTimeString()}</span>
                    </div>
                  )) : <div className="empty-state">Run an investigation to view the agent timeline.</div>}
                </div>
              </div>
              <div className="workspace-sidepanel">
                <div className="workspace-kicker">Conversation</div>
                <div className="message-list">
                  {latestMessages.length ? latestMessages.map((message) => (
                    <div key={message.message_id} className={message.role === "user" ? "message-card user" : "message-card assistant"}>
                      <strong>{message.role === "user" ? "You" : "Agent"}</strong>
                      <p>{message.content}</p>
                    </div>
                  )) : <div className="empty-state">Conversation history will appear here.</div>}
                </div>
              </div>
            </div>
          ) : null}

          {activeTab === "memory" ? (
            <div className="workspace-dual-column">
              <div className="workspace-sidepanel">
                <div className="workspace-kicker">Knowledge graph</div>
                {graphNodes.length ? (
                  <div className="graph-list">
                    {graphNodes.map((node) => (
                      <div key={node.node_id} className="graph-node">
                        <span>{node.group}</span>
                        <strong>{node.label}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">Cross-session memory will appear after a few investigations.</div>
                )}
              </div>
              <div className="workspace-sidepanel">
                <div className="workspace-kicker">Session snapshot</div>
                <div className="message-list">
                  {latestMessages.length ? latestMessages.map((message) => (
                    <div key={message.message_id} className={message.role === "user" ? "message-card user" : "message-card assistant"}>
                      <strong>{message.role === "user" ? "Question" : "Response"}</strong>
                      <p>{message.content}</p>
                    </div>
                  )) : <div className="empty-state">No messages saved yet.</div>}
                </div>
              </div>
            </div>
          ) : null}

          {!latestReport && activeTab !== "trace" && activeTab !== "memory" ? (
            <div className="empty-state workspace-empty">Run your first investigation to generate a structured report.</div>
          ) : null}
        </div>
      </div>
      )}

      {commandOpen ? (
        <div className="command-overlay" onClick={() => setCommandOpen(false)}>
          <div className="command-palette" onClick={(event) => event.stopPropagation()}>
            <div className="workspace-kicker">Command palette</div>
            <button className="command-item" onClick={() => { setCommandOpen(false); void handleCreateSession(); }}>New session</button>
            <button className="command-item" onClick={() => { setCommandOpen(false); setPrefs((state) => ({ ...state, focusMode: !state.focusMode })); }}>
              Toggle focus mode
            </button>
            <button className="command-item" onClick={() => { setCommandOpen(false); setPrefs((state) => ({ ...state, theme: state.theme === "dark" ? "light" : "dark" })); }}>
              Toggle theme
            </button>
            <button className="command-item" onClick={() => { setCommandOpen(false); void handleExport("markdown"); }} disabled={!latestReport}>
              Export latest report
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

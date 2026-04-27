import { useEffect, useMemo, useState } from "react";
import { AgentDock } from "../components/AgentDock";
import { LiveNetworkMap } from "../components/LiveNetworkMap";
import { TrendChart } from "../components/TrendChart";
import { useDashboardData } from "../hooks/useDashboardData";
import { LiveNetworkLocation } from "../types/api";
import { DashboardContext, ResearchReport } from "../types/research";

type PollutantFocus = "both" | "o3" | "no2";
type ProfileFocus = "zip_only" | "external_augmented";

type TimelinePoint = {
  timestamp: string;
  o3: number;
  no2: number;
  phase: "live" | "forecast";
};

type ExternalRunRequest = {
  nonce: number;
  query: string;
} | null;

type AgentPreviewState = {
  busy: boolean;
  report: ResearchReport | null;
  error: string | null;
  query: string;
};

const PRESET_QUERIES = [
  "Why is O3 rising?",
  "Compare Delhi with live network",
  "Explain next 24h risk",
  "Which pollutant drives the alert?",
  "Compare zip_only vs external_augmented",
];

const AGENT_PLAN = [
  "Read live station signals",
  "Compare against SIH baseline",
  "Inspect forecast horizon",
  "Check alert thresholds",
  "Compare city network",
  "Generate environmental brief",
];

function riskLabel(o3: number, no2: number) {
  if (o3 >= 140 || no2 >= 110) return "High risk";
  if (o3 >= 95 || no2 >= 70) return "Watch";
  return "Stable";
}

function metricValue(value: number) {
  return `${value.toFixed(1)} ug/m3`;
}

function compactModelName(model: string | null | undefined) {
  if (!model) return "standby";
  return model.split("_").join(" ");
}

function stripAgentContext(value: string) {
  return value.split("\n\nContext:")[0].trim();
}

function average(values: number[]) {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function trendDirection(current: number, baseline: number | null) {
  if (baseline === null) return "unknown";
  const delta = current - baseline;
  if (Math.abs(delta) < 5) return "stable";
  return delta > 0 ? "rising" : "falling";
}

function strongestDriver(o3: number, no2: number, o3Baseline: number | null, no2Baseline: number | null) {
  const o3Delta = o3Baseline === null ? Math.abs(o3) : Math.abs(o3 - o3Baseline);
  const no2Delta = no2Baseline === null ? Math.abs(no2) : Math.abs(no2 - no2Baseline);
  return o3Delta >= no2Delta ? "O3" : "NO2";
}

function sectionByKey(report: ResearchReport | null, keys: string[]) {
  if (!report) return null;
  return report.sections.find((section) => keys.includes(section.key)) ?? null;
}

export function DashboardPage() {
  const [siteId, setSiteId] = useState(1);
  const [networkScope, setNetworkScope] = useState<"india" | "global">("india");
  const [selectedNetworkKey, setSelectedNetworkKey] = useState<string | null>(null);
  const [pollutantFocus, setPollutantFocus] = useState<PollutantFocus>("both");
  const [timelineIndex, setTimelineIndex] = useState(0);
  const [horizonHours, setHorizonHours] = useState(24);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [profileFocus, setProfileFocus] = useState<ProfileFocus>("zip_only");
  const [commandQuery, setCommandQuery] = useState("");
  const [externalRunRequest, setExternalRunRequest] = useState<ExternalRunRequest>(null);
  const [agentPreview, setAgentPreview] = useState<AgentPreviewState>({
    busy: false,
    report: null,
    error: null,
    query: "",
  });
  const [replayMode, setReplayMode] = useState(false);

  const {
    summary,
    trend,
    live,
    liveNetwork,
    forecast,
    alerts,
    metadata,
    loading,
    refreshing,
    networkRefreshing,
    lastLoadedAt,
    autoRefresh,
    setAutoRefresh,
    refreshNow,
    error,
    networkError,
  } = useDashboardData(siteId, networkScope, horizonHours, selectedModel);

  useEffect(() => {
    if (!selectedModel && metadata?.active_model) {
      setSelectedModel(metadata.active_model);
    }
  }, [metadata?.active_model, selectedModel]);

  const activeSite = summary?.sites.find((site) => site.site_id === siteId) ?? null;

  const alignedForecast = useMemo(() => {
    if (!forecast || !live?.recent.length) return forecast;
    const anchor = new Date(live.recent[live.recent.length - 1].timestamp);
    return {
      ...forecast,
      points: forecast.points.map((point, index) => ({
        ...point,
        timestamp: new Date(anchor.getTime() + (index + 1) * 60 * 60 * 1000).toISOString(),
      })),
    };
  }, [forecast, live]);

  const timelinePoints = useMemo<TimelinePoint[]>(() => {
    if (!live || !alignedForecast) return [];
    return [
      ...live.recent.slice(-24).map((point) => ({
        timestamp: point.timestamp,
        o3: point.o3,
        no2: point.no2,
        phase: "live" as const,
      })),
      ...alignedForecast.points.map((point) => ({
        timestamp: point.timestamp,
        o3: point.o3,
        no2: point.no2,
        phase: "forecast" as const,
      })),
    ];
  }, [live, alignedForecast]);

  useEffect(() => {
    if (live?.recent.length) {
      setTimelineIndex(Math.max(live.recent.slice(-24).length - 1, 0));
    }
  }, [live?.recent.length, siteId, horizonHours]);

  useEffect(() => {
    if (!replayMode || timelinePoints.length <= 1) return;
    const interval = window.setInterval(() => {
      setTimelineIndex((current) => {
        if (current >= timelinePoints.length - 1) {
          window.clearInterval(interval);
          setReplayMode(false);
          return timelinePoints.length - 1;
        }
        return current + 1;
      });
    }, 180);
    return () => window.clearInterval(interval);
  }, [replayMode, timelinePoints.length]);

  const selectedPoint = timelinePoints[Math.min(timelineIndex, Math.max(timelinePoints.length - 1, 0))];
  const currentO3 = selectedPoint?.o3 ?? live?.current.o3 ?? 0;
  const currentNO2 = selectedPoint?.no2 ?? live?.current.no2 ?? 0;
  const currentRisk = riskLabel(currentO3, currentNO2);
  const selectedTimestamp = selectedPoint?.timestamp ?? null;
  const selectedLabel = selectedPoint
    ? new Date(selectedPoint.timestamp).toLocaleString(undefined, {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "sync pending";

  const rankedNetwork = useMemo(() => {
    if (!liveNetwork?.locations.length) return [];
    return [...liveNetwork.locations].sort(
      (left, right) =>
        Math.max(right.current.us_aqi ?? 0, right.current.european_aqi ?? 0) -
        Math.max(left.current.us_aqi ?? 0, left.current.european_aqi ?? 0),
    );
  }, [liveNetwork]);

  useEffect(() => {
    if (rankedNetwork.length) {
      setSelectedNetworkKey((current) => current ?? rankedNetwork[0].key);
    }
  }, [rankedNetwork]);

  const selectedNetworkLocation = useMemo<LiveNetworkLocation | null>(() => {
    if (!rankedNetwork.length) return null;
    return rankedNetwork.find((location) => location.key === selectedNetworkKey) ?? rankedNetwork[0];
  }, [rankedNetwork, selectedNetworkKey]);

  const baselineAverages = useMemo(() => {
    const recent = trend?.points.slice(-72) ?? [];
    return {
      o3: average(recent.map((point) => point.o3)),
      no2: average(recent.map((point) => point.no2)),
    };
  }, [trend]);

  const peakForecast = useMemo(() => {
    if (!alignedForecast?.points.length) return { o3: 0, no2: 0, o3Hour: "--:--", no2Hour: "--:--" };
    const topO3 = alignedForecast.points.reduce((best, point) => (point.o3 > best.o3 ? point : best), alignedForecast.points[0]);
    const topNO2 = alignedForecast.points.reduce((best, point) => (point.no2 > best.no2 ? point : best), alignedForecast.points[0]);
    return {
      o3: topO3.o3,
      no2: topNO2.no2,
      o3Hour: new Date(topO3.timestamp).toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" }),
      no2Hour: new Date(topNO2.timestamp).toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" }),
    };
  }, [alignedForecast]);

  const topAlert = alerts?.alerts[0] ?? null;
  const syncTime = lastLoadedAt ? new Date(lastLoadedAt).toLocaleTimeString() : "pending";
  const liveStatus = refreshing ? "Updating" : "Live";
  const provenanceSources = metadata?.training_data_sources?.join(" + ") ?? "SIH + OpenMeteo";
  const modelMetrics = selectedModel ? metadata?.metrics[selectedModel] ?? null : null;
  const o3Metrics = modelMetrics?.O3_target ?? null;
  const no2Metrics = modelMetrics?.NO2_target ?? null;
  const driver = strongestDriver(currentO3, currentNO2, baselineAverages.o3, baselineAverages.no2);
  const o3Direction = trendDirection(currentO3, baselineAverages.o3);
  const no2Direction = trendDirection(currentNO2, baselineAverages.no2);
  const dashboardContext = useMemo<DashboardContext>(
    () => ({
      site_id: siteId,
      station_label: `Site ${siteId}`,
      selected_timestamp: selectedTimestamp,
      selected_label: selectedLabel,
      phase: selectedPoint?.phase ?? null,
      visible_o3: Number(currentO3.toFixed(2)),
      visible_no2: Number(currentNO2.toFixed(2)),
      risk: currentRisk,
      horizon_hours: horizonHours,
      profile_focus: profileFocus,
      pollutant_focus: pollutantFocus,
      model_name: selectedModel ?? metadata?.active_model ?? "default",
      network_scope: networkScope,
      selected_city_key: selectedNetworkLocation?.key ?? null,
      selected_city_name: selectedNetworkLocation?.name ?? null,
      selected_city_label: selectedNetworkLocation
        ? `${selectedNetworkLocation.name}, ${selectedNetworkLocation.country}`
        : null,
      selected_city_o3: selectedNetworkLocation?.current.o3 ?? null,
      selected_city_no2: selectedNetworkLocation?.current.no2 ?? null,
      selected_city_aqi: selectedNetworkLocation?.current.us_aqi ?? selectedNetworkLocation?.current.european_aqi ?? null,
      forecast_peak_o3: Number(peakForecast.o3.toFixed(2)),
      forecast_peak_no2: Number(peakForecast.no2.toFixed(2)),
      forecast_peak_o3_time: peakForecast.o3Hour,
      forecast_peak_no2_time: peakForecast.no2Hour,
      alert_count: alerts?.alerts.length ?? 0,
      top_alert_pollutant: topAlert?.pollutant ?? null,
      top_alert_severity: topAlert?.severity ?? null,
      baseline_avg_o3: baselineAverages.o3 === null ? null : Number(baselineAverages.o3.toFixed(2)),
      baseline_avg_no2: baselineAverages.no2 === null ? null : Number(baselineAverages.no2.toFixed(2)),
    }),
    [
      alerts?.alerts.length,
      baselineAverages.no2,
      baselineAverages.o3,
      currentNO2,
      currentO3,
      currentRisk,
      horizonHours,
      metadata?.active_model,
      networkScope,
      peakForecast.no2,
      peakForecast.no2Hour,
      peakForecast.o3,
      peakForecast.o3Hour,
      pollutantFocus,
      profileFocus,
      selectedLabel,
      selectedModel,
      selectedNetworkLocation,
      selectedPoint?.phase,
      selectedTimestamp,
      siteId,
      topAlert?.pollutant,
      topAlert?.severity,
    ],
  );

  function triggerAgentRun(nextQuery: string) {
    const trimmed = stripAgentContext(nextQuery);
    if (!trimmed) return;
    setCommandQuery(trimmed);
    setAgentPreview((current) => ({
      ...current,
      busy: true,
      error: null,
      query: trimmed,
    }));
    setExternalRunRequest({
      nonce: Date.now(),
      query: `${trimmed}\n\nContext:\n- Station: Site ${siteId}\n- City network scope: ${networkScope}\n- Pollutant focus: ${pollutantFocus}\n- Forecast window: ${horizonHours} hours\n- Profile focus: ${profileFocus}\n- Model: ${selectedModel ?? metadata?.active_model ?? "default"}`,
    });
  }

  function investigateAnomaly(point: { timestamp: string; pollutant: "O3" | "NO2"; value: number }) {
    const readableTime = new Date(point.timestamp).toLocaleString();
    triggerAgentRun(
      `Investigate this ${point.pollutant} anomaly at ${readableTime}: value ${point.value.toFixed(
        1,
      )} ug/m3. Compare it with baseline, forecast, alert thresholds, and the live city network.`,
    );
  }

  async function copyPreviewBrief() {
    if (!agentPreview.report) return;
    await navigator.clipboard.writeText(agentPreview.report.summary_markdown);
  }

  function jumpToInvestigation() {
    document.getElementById("agent-investigation")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const answerDecision = sectionByKey(agentPreview.report, ["alert", "network", "outlook", "situation"]);
  const answerEvidence = sectionByKey(agentPreview.report, ["situation", "dataset", "network"]);
  const answerActions = sectionByKey(agentPreview.report, ["actions", "unknowns"]);

  if (!loading && error) {
    return (
      <main className="command-shell loading">
        <div className="command-grid" />
        <div className="load-error-shell">
          <div className="mono-label">Data connection failed</div>
          <h1>Backend data could not load.</h1>
          <p>{error}</p>
          <button type="button" className="investigate-button" onClick={() => refreshNow()}>
            Retry
          </button>
        </div>
      </main>
    );
  }

  if (loading || !summary || !trend || !live || !alignedForecast || !alerts || !metadata || !activeSite) {
    return (
      <main className="command-shell loading">
        <div className="command-grid" />
        <div className="loading-shell">
          <div className="loading-line long" />
          <div className="loading-line medium" />
          <div className="loading-line short" />
        </div>
      </main>
    );
  }

  return (
    <main className="command-shell">
      <div className="command-grid" />
      <div className="command-glow hero-left" />
      <div className="command-glow hero-right" />

      <header className="command-nav">
        <div className="brand-lockup">
          <div className="brand-mark">A</div>
          <div>
            <div className="brand-name">AeroIntel</div>
            <div className="brand-subtitle">autonomous air-quality agent</div>
          </div>
        </div>

        <div className="nav-meta">
          <span className="nav-live">
            <span className="nav-dot" />
            {liveStatus}
          </span>
          <span>{compactModelName(selectedModel ?? metadata.active_model)}</span>
          <span>{syncTime}</span>
          <div className="nav-profile-switch">
            {(["zip_only", "external_augmented"] as const).map((profile) => (
              <button
                key={profile}
                type="button"
                className={profile === profileFocus ? "nav-profile active" : "nav-profile"}
                onClick={() => setProfileFocus(profile)}
              >
                {profile}
              </button>
            ))}
          </div>
        </div>
      </header>

      <section className="hero-stage">
        <div className="hero-pill">Real-time - Forecasting - Agentic</div>
        <h1 className="hero-title">
          Forecast air quality. <span>Precisely.</span>
        </h1>
        <p className="hero-subtitle">
          An autonomous air-quality agent that monitors live O3 / NO2 signals, compares forecast models,
          investigates pollution drivers, and generates confidence-scored environmental briefs in real time.
        </p>

        <div className="hero-metrics">
          <div>
            <span>O3</span>
            <strong>{metricValue(currentO3)}</strong>
          </div>
          <div>
            <span>NO2</span>
            <strong>{metricValue(currentNO2)}</strong>
          </div>
          <div>
            <span>Risk</span>
            <strong>{currentRisk}</strong>
          </div>
          <div>
            <span>Station</span>
            <strong>Site {siteId}</strong>
          </div>
        </div>

        <div className="command-surface">
          <div className="surface-selector-row">
            <div className="surface-selector-group">
              <span>Station</span>
              <div className="surface-inline-options">
                {summary.sites.map((site) => (
                  <button
                    key={site.site_id}
                    type="button"
                    className={site.site_id === siteId ? "surface-option active" : "surface-option"}
                    onClick={() => setSiteId(site.site_id)}
                  >
                    Site {site.site_id}
                  </button>
                ))}
              </div>
            </div>
            <div className="surface-selector-group">
              <span>City</span>
              <div className="surface-inline-options">
                {(["india", "global"] as const).map((scope) => (
                  <button
                    key={scope}
                    type="button"
                    className={scope === networkScope ? "surface-option active" : "surface-option"}
                    onClick={() => setNetworkScope(scope)}
                  >
                    {scope}
                  </button>
                ))}
              </div>
            </div>
            <div className="surface-selector-group">
              <span>Pollutant</span>
              <div className="surface-inline-options">
                {(["both", "o3", "no2"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={mode === pollutantFocus ? "surface-option active" : "surface-option"}
                    onClick={() => setPollutantFocus(mode)}
                  >
                    {mode === "both" ? "both" : mode.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="surface-selector-group">
              <span>Forecast window</span>
              <div className="surface-inline-options">
                {[12, 24, 48].map((hours) => (
                  <button
                    key={hours}
                    type="button"
                    className={hours === horizonHours ? "surface-option active" : "surface-option"}
                    onClick={() => setHorizonHours(hours)}
                  >
                    {hours}h
                  </button>
                ))}
              </div>
            </div>
            <div className="surface-selector-group">
              <span>Model profile</span>
              <div className="surface-inline-options">
                {(metadata.available_models.length ? metadata.available_models : [metadata.active_model]).map((model) => (
                  <button
                    key={model}
                    type="button"
                    className={model === selectedModel ? "surface-option active" : "surface-option"}
                    onClick={() => setSelectedModel(model)}
                  >
                    {compactModelName(model)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="surface-input-row">
            <div className="surface-input-shell">
              <span className="surface-prompt">ask</span>
              <input
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    triggerAgentRun(commandQuery);
                  }
                }}
                placeholder="Ask about O3 spikes, NO2 drift, forecast risk, or station behavior..."
              />
            </div>
            <button type="button" className="investigate-button" onClick={() => triggerAgentRun(commandQuery)}>
              Investigate -&gt;
            </button>
          </div>

          <div className="surface-chip-row">
            {PRESET_QUERIES.map((preset) => (
              <button
                key={preset}
                type="button"
                className="surface-chip"
                onClick={() => {
                  setCommandQuery(preset);
                  triggerAgentRun(preset);
                }}
              >
                {preset}
              </button>
            ))}
          </div>

          <div className="agent-loop-preview">
            <div className="agent-loop-label">agent loop</div>
            <ol>
              {AGENT_PLAN.map((step, index) => (
                <li key={step}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          {(agentPreview.busy || agentPreview.report || agentPreview.error) && (
            <div className="surface-result-preview">
              <div className="result-preview-header">
                <div>
                  <span className="mono-label">{agentPreview.busy ? "Investigation running" : "Latest answer"}</span>
                  <h2>
                    {agentPreview.busy
                      ? "Reading live signals and forecast evidence..."
                      : agentPreview.report?.title ?? "Investigation interrupted"}
                  </h2>
                </div>
                {agentPreview.report ? (
                  <div className="result-confidence">
                    <span>confidence</span>
                    <strong>{Math.round(agentPreview.report.confidence.overall * 100)}%</strong>
                  </div>
                ) : null}
              </div>

              {agentPreview.error ? <p className="result-error">{agentPreview.error}</p> : null}
              {agentPreview.busy ? (
                <div className="result-progress-lines">
                  <span />
                  <span />
                  <span />
                </div>
              ) : null}
              {agentPreview.report ? (
                <>
                  <div className="answer-cockpit">
                    <div className="answer-primary">
                      <span className="answer-badge">dashboard-synced</span>
                      <p className="result-overview">{agentPreview.report.overview}</p>
                      {answerDecision ? (
                        <div className="answer-verdict">
                          <span>{answerDecision.title}</span>
                          <strong>{answerDecision.content}</strong>
                        </div>
                      ) : null}
                    </div>
                    <aside className="answer-evidence-rail">
                      <div>
                        <span>visible O3</span>
                        <strong>{currentO3.toFixed(1)}</strong>
                        <em>{o3Direction}</em>
                      </div>
                      <div>
                        <span>visible NO2</span>
                        <strong>{currentNO2.toFixed(1)}</strong>
                        <em>{no2Direction}</em>
                      </div>
                      <div>
                        <span>driver</span>
                        <strong>{driver}</strong>
                        <em>{currentRisk}</em>
                      </div>
                    </aside>
                  </div>
                  <div className="answer-structured-grid">
                    {[answerEvidence, answerActions].filter(Boolean).map((section) => (
                      <div key={section!.key}>
                        <span>{section!.title}</span>
                        <p>{section!.content}</p>
                      </div>
                    ))}
                  </div>
                  <div className="result-actions">
                    <button type="button" className="text-action" onClick={() => void copyPreviewBrief()}>
                      Copy brief
                    </button>
                    <button type="button" className="text-action" onClick={jumpToInvestigation}>
                      Open audit trace
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          )}
        </div>
      </section>

      <section className="intelligence-zones" aria-label="Operational intelligence structure">
        <div className="zone-label">
          <span className="mono-label">Unified decision layer</span>
          <h2>Inputs, live activity, final answer, and evidence stay in one rhythm.</h2>
        </div>
        <div className="zone-rail">
          <div className="zone-block active">
            <span>01 input</span>
            <strong>{commandQuery || "Ask a forecast question"}</strong>
            <em>context auto-injected from visible dashboard state</em>
          </div>
          <div className={agentPreview.busy ? "zone-block active" : "zone-block"}>
            <span>02 live activity</span>
            <strong>{agentPreview.busy ? "investigating" : "ready"}</strong>
            <em>step trace, retry targets, source checks</em>
          </div>
          <div className={agentPreview.report ? "zone-block active" : "zone-block"}>
            <span>03 final output</span>
            <strong>{agentPreview.report?.title ?? "awaiting brief"}</strong>
            <em>overview, insight, risk, action</em>
          </div>
          <div className="zone-block">
            <span>04 evidence</span>
            <strong>{selectedNetworkLocation?.name ?? "network sync"}</strong>
            <em>SIH baseline + forecast + alerts + live network</em>
          </div>
        </div>
        <div className="intelligence-matrix">
          <div>
            <span>momentum</span>
            <strong>
              O3 {o3Direction} / NO2 {no2Direction}
            </strong>
          </div>
          <div>
            <span>watch driver</span>
            <strong>{driver}</strong>
          </div>
          <div>
            <span>forecast deviation</span>
            <strong>
              O3 {(peakForecast.o3 - currentO3).toFixed(1)} · NO2 {(peakForecast.no2 - currentNO2).toFixed(1)}
            </strong>
          </div>
          <div>
            <span>confidence posture</span>
            <strong>{agentPreview.report ? `${Math.round(agentPreview.report.confidence.overall * 100)}%` : "model ready"}</strong>
          </div>
        </div>
      </section>

      <section className="command-center-strip">
        <div className="strip-leading">
          <span className="mono-label">Forecast command center</span>
          <h2>See what the air does next.</h2>
        </div>
        <div className="strip-metrics">
          <div>
            <span>Peak O3</span>
            <strong>{peakForecast.o3.toFixed(1)}</strong>
            <em>{peakForecast.o3Hour}</em>
          </div>
          <div>
            <span>Peak NO2</span>
            <strong>{peakForecast.no2.toFixed(1)}</strong>
            <em>{peakForecast.no2Hour}</em>
          </div>
          <div>
            <span>Alert state</span>
            <strong>{topAlert ? topAlert.severity : "calm"}</strong>
            <em>{topAlert ? topAlert.pollutant : "none"}</em>
          </div>
          <div>
            <span>Live hotspot</span>
            <strong>{selectedNetworkLocation?.name ?? "pending"}</strong>
            <em>{selectedNetworkLocation?.country ?? "--"}</em>
          </div>
        </div>
      </section>

      <section className="timeline-stage">
        <div className="timeline-header">
          <div>
            <div className="mono-label">Forecast timeline</div>
            <h3>Historical, live, and forecasted movement on one rail.</h3>
          </div>
          <div className="timeline-controls">
            <button
              type="button"
              className={autoRefresh ? "timeline-text-toggle active" : "timeline-text-toggle"}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              {autoRefresh ? "auto sync on" : "auto sync off"}
            </button>
            <button type="button" className="timeline-text-toggle" onClick={() => setReplayMode(true)}>
              replay forecast
            </button>
            <button
              type="button"
              className="timeline-text-toggle"
              onClick={() => triggerAgentRun("Explain the current alert logic and what pollutant is driving it.")}
            >
              explain alert
            </button>
          </div>
        </div>

        <TrendChart
          historical={trend.points}
          live={live.recent}
          forecast={alignedForecast.points}
          networkLive={selectedNetworkLocation?.recent ?? []}
          pollutantFocus={pollutantFocus}
          selectedTimestamp={selectedTimestamp}
          onInvestigatePoint={investigateAnomaly}
        />

        <div className="timeline-slider-overlay">
          <div className="timeline-slider-meta">
            <span>Observed window</span>
            <span>{selectedLabel}</span>
            <span>{selectedPoint?.phase === "forecast" ? "Forecast horizon" : "Live handoff"}</span>
          </div>
          <input
            className="timeline-slider"
            type="range"
            min={0}
            max={Math.max(timelinePoints.length - 1, 0)}
            value={timelineIndex}
            onChange={(event) => setTimelineIndex(Number(event.target.value))}
          />
        </div>
      </section>

      <section className="network-and-brief">
        <div className="network-column">
          <div className="section-header">
            <div className="mono-label">Live network map</div>
            <h3>Real-time city context around the selected station.</h3>
          </div>
          {networkError ? <div className="network-error-line">{networkError}</div> : null}
          <LiveNetworkMap
            locations={rankedNetwork}
            scope={networkScope}
            onScopeChange={setNetworkScope}
            selectedKey={selectedNetworkKey}
            onSelectLocation={setSelectedNetworkKey}
          />
        </div>

        <div className="brief-column">
          <div className="section-header">
            <div className="mono-label">Model provenance</div>
            <h3>Trust the forecast because the evidence stays visible.</h3>
          </div>
          <div className="provenance-list">
            <div>
              <span>active model</span>
              <strong>{compactModelName(selectedModel ?? metadata.active_model)}</strong>
            </div>
            <div>
              <span>profile focus</span>
              <strong>{profileFocus}</strong>
            </div>
            <div>
              <span>data sources</span>
              <strong>{provenanceSources}</strong>
            </div>
            <div>
              <span>selected station</span>
              <strong>
                Site {siteId} - {activeSite.latitude.toFixed(3)}, {activeSite.longitude.toFixed(3)}
              </strong>
            </div>
            <div>
              <span>O3 metrics</span>
              <strong>
                RMSE {o3Metrics?.rmse?.toFixed(2) ?? "--"} - MAE {o3Metrics?.mae?.toFixed(2) ?? "--"} - R2{" "}
                {o3Metrics?.r2?.toFixed(2) ?? "--"}
              </strong>
            </div>
            <div>
              <span>NO2 metrics</span>
              <strong>
                RMSE {no2Metrics?.rmse?.toFixed(2) ?? "--"} - MAE {no2Metrics?.mae?.toFixed(2) ?? "--"} - R2{" "}
                {no2Metrics?.r2?.toFixed(2) ?? "--"}
              </strong>
            </div>
          </div>

          <div className="insight-rail">
            <div className="insight-line">
              <span className={`insight-dot ${currentRisk.toLowerCase().replace(" ", "-")}`} />
              <span>Forecast risk: {currentRisk.toUpperCase()}</span>
            </div>
            <div className="insight-line">
              <span className="insight-dot glow" />
              <span>Peak expected: O3 {peakForecast.o3Hour} - NO2 {peakForecast.no2Hour}</span>
            </div>
            <div className="insight-line">
              <span className="insight-dot warm" />
              <span>
                {currentNO2 > currentO3
                  ? "NO2 is currently driving the sharper divergence."
                  : "O3 is currently the stronger visible signal."}
              </span>
            </div>
            <div className="insight-line">
              <span className="insight-dot cool" />
              <span>
                {selectedNetworkLocation
                  ? `${selectedNetworkLocation.name} is the active comparison city in the ${networkScope} live network.`
                  : "Network context is syncing."}
              </span>
            </div>
            <div className="insight-line">
              <span className="insight-dot neutral" />
              <span>{topAlert ? topAlert.message : "No configured threshold exceedance is active right now."}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="agent-terminal-stage" id="agent-investigation">
        <div className="section-header">
          <div className="mono-label">Agent investigation panel</div>
          <h3>Investigation trace, evidence, confidence, and exportable output.</h3>
        </div>
        <AgentDock
          siteId={siteId}
          networkScope={networkScope}
          modelName={selectedModel ?? metadata.active_model}
          profileFocus={profileFocus}
          pollutantFocus={pollutantFocus}
          horizonHours={horizonHours}
          selectedCityLabel={selectedNetworkLocation ? `${selectedNetworkLocation.name}, ${selectedNetworkLocation.country}` : null}
          dashboardContext={dashboardContext}
          externalRunRequest={externalRunRequest}
          onAdoptQuery={(query) => setCommandQuery(stripAgentContext(query))}
          onInvestigationUpdate={setAgentPreview}
        />
      </section>

      <footer className="command-footer">
        <span>
          Model: {compactModelName(selectedModel ?? metadata.active_model)} | Data: {provenanceSources} | Live sync: {syncTime}
        </span>
        <button type="button" className="footer-action" onClick={() => refreshNow()}>
          Refresh
        </button>
      </footer>
    </main>
  );
}

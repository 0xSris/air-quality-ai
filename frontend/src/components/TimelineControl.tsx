interface TimelineControlProps {
  sliderValue: number;
  sliderMax: number;
  onSliderChange: (value: number) => void;
  selectedLabel: string;
  selectedPhase: string;
  autoRefresh: boolean;
  onAutoRefreshChange: (value: boolean) => void;
  refreshIntervalMs: number;
  onRefreshIntervalChange: (value: number) => void;
  lastLoadedAt: string | null;
  refreshing: boolean;
  onRefresh: () => void;
}

export function TimelineControl({
  sliderValue,
  sliderMax,
  onSliderChange,
  selectedLabel,
  selectedPhase,
  autoRefresh,
  onAutoRefreshChange,
  refreshIntervalMs,
  onRefreshIntervalChange,
  lastLoadedAt,
  refreshing,
  onRefresh,
}: TimelineControlProps) {
  return (
    <section className="panel timeline-panel">
      <div className="panel-header">
        <h3>Time Navigator</h3>
        <div className="panel-chips">
          <span className="panel-chip">{selectedPhase}</span>
          <span className="panel-chip">{refreshing ? "Refreshing..." : "Stable"}</span>
        </div>
      </div>
      <div className="control-grid">
        <label className="control-card">
          <span>Auto refresh</span>
          <input type="checkbox" checked={autoRefresh} onChange={(event) => onAutoRefreshChange(event.target.checked)} />
        </label>
        <label className="control-card">
          <span>Cadence</span>
          <select value={refreshIntervalMs} onChange={(event) => onRefreshIntervalChange(Number(event.target.value))}>
            <option value={10000}>10s</option>
            <option value={15000}>15s</option>
            <option value={30000}>30s</option>
            <option value={60000}>60s</option>
          </select>
        </label>
        <button className="ghost-button control-card refresh-card" onClick={onRefresh}>
          Refresh Now
        </button>
      </div>
      <div className="timeline-labels">
        <span className="timeline-label left">24h ago</span>
        <span className="timeline-label center">Now</span>
        <span className="timeline-label right">Next 24h</span>
      </div>
      <input
        className="timeline-slider"
        type="range"
        min={0}
        max={sliderMax}
        value={sliderValue}
        onChange={(event) => onSliderChange(Number(event.target.value))}
      />
      <div className="timeline-caption-row">
        <div>
          <div className="timeline-caption-title">Selected moment</div>
          <div className="timeline-caption">{selectedLabel}</div>
        </div>
        <div>
          <div className="timeline-caption-title">Latest sync</div>
          <div className="timeline-caption">{lastLoadedAt ? new Date(lastLoadedAt).toLocaleTimeString() : "Cold start"}</div>
        </div>
      </div>
    </section>
  );
}

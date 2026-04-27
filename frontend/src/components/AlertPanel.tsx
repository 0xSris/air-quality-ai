import { AlertItem } from "../types/api";

export function AlertPanel({ alerts }: { alerts: AlertItem[] }) {
  const criticalCount = alerts.filter((alert) => alert.severity === "critical").length;
  const warningCount = alerts.filter((alert) => alert.severity === "warning").length;
  const infoCount = alerts.filter((alert) => alert.severity === "info").length;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>What Needs Attention</h3>
          <p className="panel-copy">Threshold-based warnings for the selected Delhi forecast station.</p>
        </div>
        <div className="panel-chips">
          <span className="panel-chip">Critical {criticalCount}</span>
          <span className="panel-chip">Warning {warningCount}</span>
          <span className="panel-chip">Info {infoCount}</span>
        </div>
      </div>
      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="empty-state">No major threshold exceedances are expected in the upcoming forecast window.</div>
        ) : (
          alerts.slice(0, 8).map((alert, index) => (
            <div key={`${alert.site_id}-${alert.timestamp}-${index}`} className={`alert-card ${alert.severity}`}>
              <div className="alert-badge">{alert.pollutant}</div>
              <div>
                <div className="alert-message">{alert.message}</div>
                <div className="alert-meta">
                  Site {alert.site_id} | {new Date(alert.timestamp).toLocaleString()} | {alert.value.toFixed(1)} ug/m3
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

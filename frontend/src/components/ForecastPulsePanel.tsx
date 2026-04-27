import { ForecastPoint } from "../types/api";

function severityLabel(o3: number, no2: number) {
  if (o3 >= 140 || no2 >= 110) return "High risk";
  if (o3 >= 95 || no2 >= 70) return "Elevated";
  return "Stable";
}

export function ForecastPulsePanel({
  forecast,
}: {
  forecast: ForecastPoint[];
}) {
  const rankedHours = [...forecast]
    .map((point) => ({
      ...point,
      score: point.o3 * 0.65 + point.no2 * 0.35,
      severity: severityLabel(point.o3, point.no2),
    }))
    .sort((left, right) => right.score - left.score)
    .slice(0, 4);

  return (
    <section className="panel pulse-panel">
      <div className="panel-header">
        <div>
          <h3>Forecast Pulse</h3>
          <p className="panel-copy">The strongest upcoming windows ranked by combined pollutant pressure.</p>
        </div>
      </div>
      <div className="pulse-list">
        {rankedHours.map((point, index) => (
          <div key={`${point.timestamp}-${index}`} className="pulse-card">
            <div className="pulse-rank">#{index + 1}</div>
            <div className="pulse-main">
              <div className="pulse-time">{new Date(point.timestamp).toLocaleString()}</div>
              <div className="pulse-metrics">
                <span>O3 {point.o3.toFixed(1)}</span>
                <span>NO2 {point.no2.toFixed(1)}</span>
                <span>{point.severity}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

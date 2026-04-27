import { LiveNetworkLocation, PollutantPoint } from "../types/api";

function formatDelta(value: number) {
  const rounded = Math.abs(value).toFixed(1);
  return value > 0 ? `+${rounded}` : `-${rounded}`;
}

export function ComparisonPanel({
  stationName,
  stationPoint,
  city,
}: {
  stationName: string;
  stationPoint: PollutantPoint;
  city: LiveNetworkLocation | null;
}) {
  if (!city) {
    return (
      <section className="panel comparison-panel">
        <div className="panel-header">
          <div>
            <h3>Station vs City</h3>
            <p className="panel-copy">Choose a live network city to compare it with the active Delhi station.</p>
          </div>
        </div>
        <div className="empty-state">No live city selected yet.</div>
      </section>
    );
  }

  const o3Delta = city.current.o3 - stationPoint.o3;
  const no2Delta = city.current.no2 - stationPoint.no2;
  const aqiDelta = (city.current.us_aqi ?? 0) - (stationPoint.us_aqi ?? 0);

  return (
    <section className="panel comparison-panel">
      <div className="panel-header">
        <div>
          <h3>Station vs City</h3>
          <p className="panel-copy">{stationName} compared with the selected live city.</p>
        </div>
      </div>
      <div className="comparison-grid">
        <div className="comparison-card">
          <div className="comparison-label">{stationName}</div>
          <div className="comparison-value">O3 {stationPoint.o3.toFixed(1)} | NO2 {stationPoint.no2.toFixed(1)}</div>
          <div className="comparison-subtle">US AQI {stationPoint.us_aqi?.toFixed(0) ?? "n/a"}</div>
        </div>
        <div className="comparison-card">
          <div className="comparison-label">{city.name}, {city.country}</div>
          <div className="comparison-value">O3 {city.current.o3.toFixed(1)} | NO2 {city.current.no2.toFixed(1)}</div>
          <div className="comparison-subtle">US AQI {city.current.us_aqi?.toFixed(0) ?? "n/a"}</div>
        </div>
      </div>
      <div className="comparison-deltas">
        <div className="delta-pill">O3 delta {formatDelta(o3Delta)}</div>
        <div className="delta-pill">NO2 delta {formatDelta(no2Delta)}</div>
        <div className="delta-pill">AQI delta {formatDelta(aqiDelta)}</div>
      </div>
      <div className="comparison-note">
        {Math.abs(o3Delta) > Math.abs(no2Delta)
          ? "O3 is the main separator between the selected station and city right now."
          : "NO2 is the main separator between the selected station and city right now."}
      </div>
    </section>
  );
}

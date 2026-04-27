import { AlertItem, LiveNetworkLocation } from "../types/api";

type InsightStreamProps = {
  riskLabel: string;
  selectedLabel: string;
  peakO3: number;
  peakNO2: number;
  selectedNetworkLocation: LiveNetworkLocation | null;
  alerts: AlertItem[];
  activeModel: string;
};

function topAlert(alerts: AlertItem[]) {
  return [...alerts].sort((left, right) => {
    const severityWeight = { critical: 3, warning: 2, info: 1 };
    return severityWeight[right.severity] - severityWeight[left.severity];
  })[0];
}

export function InsightStream({
  riskLabel,
  selectedLabel,
  peakO3,
  peakNO2,
  selectedNetworkLocation,
  alerts,
  activeModel,
}: InsightStreamProps) {
  const leadAlert = topAlert(alerts);
  const highestPollutant = peakO3 >= peakNO2 ? "O3" : "NO2";
  const peakLead = highestPollutant === "O3" ? peakO3 : peakNO2;

  const lines = [
    {
      tone: riskLabel === "High risk" ? "hot" : riskLabel === "Elevated" ? "warm" : "cool",
      label: "Forecast risk",
      value: riskLabel.toUpperCase(),
      meta: selectedLabel,
    },
    {
      tone: "cool",
      label: "Peak expected",
      value: `${highestPollutant} ${peakLead.toFixed(1)} ug/m3`,
      meta: "Dominant pollutant window",
    },
    {
      tone: selectedNetworkLocation ? "warm" : "cool",
      label: "Network divergence",
      value: selectedNetworkLocation
        ? `${selectedNetworkLocation.name}, ${selectedNetworkLocation.country}`
        : "No comparison city selected",
      meta: selectedNetworkLocation
        ? `O3 ${selectedNetworkLocation.current.o3.toFixed(1)} · NO2 ${selectedNetworkLocation.current.no2.toFixed(1)}`
        : "Live network standby",
    },
    {
      tone: leadAlert ? (leadAlert.severity === "critical" ? "hot" : "warm") : "cool",
      label: "Alert layer",
      value: leadAlert ? `${leadAlert.pollutant} ${leadAlert.severity}` : "No active threshold signal",
      meta: leadAlert ? leadAlert.message : "Thresholds are currently quiet",
    },
    {
      tone: "cool",
      label: "Model",
      value: activeModel.split("_").join(" "),
      meta: "Serving current forecast horizon",
    },
  ];

  return (
    <aside className="insight-stream" aria-label="Insight stream">
      {lines.map((line) => (
        <div key={line.label} className={`insight-line ${line.tone}`}>
          <div className="insight-line-kicker">{line.label}</div>
          <div className="insight-line-value">{line.value}</div>
          <div className="insight-line-meta">{line.meta}</div>
        </div>
      ))}
    </aside>
  );
}

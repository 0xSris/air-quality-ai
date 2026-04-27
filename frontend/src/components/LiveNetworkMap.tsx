import "leaflet/dist/leaflet.css";
import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer } from "react-leaflet";
import { LiveNetworkLocation } from "../types/api";

type LiveNetworkMapProps = {
  locations: LiveNetworkLocation[];
  scope: "india" | "global";
  onScopeChange: (value: "india" | "global") => void;
  selectedKey: string | null;
  onSelectLocation: (key: string) => void;
};

function modeledAqi(location: LiveNetworkLocation) {
  return location.current.us_aqi?.toFixed(0) ?? "n/a";
}

function tone(location: LiveNetworkLocation) {
  const score = Math.max(location.current.us_aqi ?? 0, location.current.european_aqi ?? 0);
  if (score >= 160) return "#ff7a59";
  if (score >= 120) return "#ffd36f";
  if (score >= 80) return "#7ee4ff";
  return "#6af2c4";
}

export function LiveNetworkMap({
  locations,
  scope,
  onScopeChange,
  selectedKey,
  onSelectLocation,
}: LiveNetworkMapProps) {
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const selectedLocation = useMemo(
    () => locations.find((location) => location.key === (hoveredKey ?? selectedKey)) ?? locations[0] ?? null,
    [hoveredKey, selectedKey, locations],
  );

  const center =
    scope === "india"
      ? ([22.8, 79.8] as [number, number])
      : ([25.2, 48.4] as [number, number]);

  return (
    <section className="network-layer">
      <div className="network-layer-header">
        <div className="network-layer-title">Live network</div>
        <div className="network-scope-switch">
          <button className={scope === "india" ? "network-scope active" : "network-scope"} onClick={() => onScopeChange("india")}>
            India
          </button>
          <button className={scope === "global" ? "network-scope active" : "network-scope"} onClick={() => onScopeChange("global")}>
            Global
          </button>
        </div>
      </div>

      <div className="network-layer-stage">
        <MapContainer
          key={`${scope}-${selectedKey ?? "none"}`}
          center={center}
          zoom={scope === "india" ? 4.8 : 2.1}
          scrollWheelZoom={false}
          style={{ height: 380, width: "100%" }}
          attributionControl={false}
        >
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          {locations.map((location) => {
            const active = location.key === (hoveredKey ?? selectedKey);
            const color = tone(location);
            return (
              <CircleMarker
                key={location.key}
                center={[location.latitude, location.longitude]}
                radius={active ? 11 : 8}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: active ? 0.92 : 0.72,
                  weight: active ? 2 : 1,
                }}
                eventHandlers={{
                  mouseover: () => setHoveredKey(location.key),
                  mouseout: () => setHoveredKey(null),
                  click: () => onSelectLocation(location.key),
                }}
              />
            );
          })}
        </MapContainer>

        <div className="network-inline-readout">
          <div className="network-inline-kicker">
            {selectedLocation ? `${selectedLocation.name}, ${selectedLocation.country}` : "Live network standby"}
          </div>
          <div className="network-inline-values">
            {selectedLocation
              ? `Modeled US AQI ${modeledAqi(selectedLocation)} - O3 ${selectedLocation.current.o3.toFixed(1)} - NO2 ${selectedLocation.current.no2.toFixed(1)}`
              : "Awaiting live network points"}
          </div>
          <div className="network-inline-source">Open-Meteo CAMS estimate, not CPCB official AQI</div>
        </div>
      </div>

      <div className="network-text-list">
        {locations.slice(0, 7).map((location, index) => (
          <button
            key={location.key}
            type="button"
            className={location.key === selectedKey ? "network-text-row active" : "network-text-row"}
            onMouseEnter={() => setHoveredKey(location.key)}
            onMouseLeave={() => setHoveredKey(null)}
            onClick={() => onSelectLocation(location.key)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <span>{location.name}</span>
            <span title="Modeled US AQI estimate">{modeledAqi(location)}</span>
            <span>{location.current.o3.toFixed(1)}</span>
            <span>{location.current.no2.toFixed(1)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { SiteSummary } from "../types/api";

export function SiteMap({
  sites,
  activeSiteId,
  onSelect,
}: {
  sites: SiteSummary[];
  activeSiteId: number;
  onSelect: (siteId: number) => void;
}) {
  return (
    <section className="panel map-panel">
      <div className="panel-header">
        <div>
          <h3>Delhi Forecast Stations</h3>
          <p className="panel-copy">These are the ground-truth SIH monitoring locations used for training and local forecasting.</p>
        </div>
        <div className="panel-chips">
          <span className="panel-chip">7 stations</span>
          <span className="panel-chip">Delhi NCR</span>
        </div>
      </div>
      <MapContainer center={[28.65, 77.18]} zoom={10} scrollWheelZoom={false} style={{ height: 360 }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {sites.map((site) => (
          <CircleMarker
            key={site.site_id}
            center={[site.latitude, site.longitude]}
            radius={site.site_id === activeSiteId ? 12 : 8}
            pathOptions={{
              color: site.site_id === activeSiteId ? "#f6a04d" : "#54c6b7",
              fillOpacity: 0.85,
            }}
            eventHandlers={{ click: () => onSelect(site.site_id) }}
          >
            <Popup>
              Site {site.site_id}
              <br />
              Train rows: {site.train_rows}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="map-site-list">
        {sites.map((site) => (
          <button
            key={site.site_id}
            className={site.site_id === activeSiteId ? "mini-site-chip active" : "mini-site-chip"}
            onClick={() => onSelect(site.site_id)}
          >
            Site {site.site_id}
          </button>
        ))}
      </div>
    </section>
  );
}

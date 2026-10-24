import Icon from "./Icon.jsx";

const LABEL_ICON = { home: "🏠", office: "🏢" };

function Stop({ kind, place }) {
  const title = place.label ? `${LABEL_ICON[place.label] ?? "📍"} ${place.label}` : place.name;
  return (
    <div className={`ride-stop ${kind}`}>
      <span className="ride-dot" />
      <div>
        <div className="ride-stop-name">{title}</div>
        <div className="ride-stop-address">{place.address}</div>
      </div>
    </div>
  );
}

// Ride planned by location assist. A preview is the draft the user confirms first;
// only the confirmed ride carries the deep links (Uber, Google Maps).
export default function RideCard({ ride }) {
  const delay = ride.duration_min - ride.typical_min;
  return (
    <div className={`ride-card${ride.preview ? " preview" : ""}`}>
      <div className="ride-head">
        {ride.preview ? (
          <span className="ride-badge draft">Check details</span>
        ) : (
          <span className="ride-badge ready">Ready to book</span>
        )}
      </div>
      <div className="ride-route">
        <Stop kind="from" place={ride.origin} />
        <Stop kind="to" place={ride.destination} />
      </div>
      <div className="ride-stats">
        <span>
          <strong>{ride.distance_km} km</strong>
        </span>
        <span>
          <strong>{ride.duration_min} min</strong> with traffic
        </span>
        {delay > 2 && <span className="ride-delay">+{delay} min vs usual</span>}
      </div>
      {ride.preview ? (
        <p className="ride-hint">Pickup and drop right? Tap Confirm below, or tell me what to change.</p>
      ) : (
        <div className="ride-actions">
          <a className="uber-btn" href={ride.uber_url} target="_blank" rel="noopener noreferrer">
            Open in Uber
          </a>
          <a className="ghost-btn" href={ride.maps_url} target="_blank" rel="noopener noreferrer">
            <Icon name="map" size={15} /> Google Maps
          </a>
        </div>
      )}
    </div>
  );
}

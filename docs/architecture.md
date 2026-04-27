# Architecture

## System overview

The platform is split into five major layers:

1. Data ingestion and validation
2. Feature engineering and model training
3. Inference and live replay services
4. FastAPI serving layer
5. React dashboard

## Flow

```text
Raw ZIP / CSV files
  -> ingestion pipeline
  -> validated canonical dataset
  -> feature engineering
  -> temporal split
  -> baseline + LSTM training
  -> artifacts + metrics + metadata
  -> backend services
  -> live simulation + forecasting APIs
  -> frontend dashboard
```

## Backend responsibilities

- load processed datasets and artifacts
- expose typed REST endpoints
- provide live simulated measurements
- compute alerts and summary analytics
- centralize configuration and logging

## ML responsibilities

- parse source files into canonical tables
- validate schema and recover temporal order
- engineer robust lag-based features
- train interchangeable model backends
- persist artifacts for runtime inference
- evaluate pollutant-specific performance

## Frontend responsibilities

- visualize current, historical, live, and forecast states
- support site selection and timeline playback
- communicate uncertainty and alert severity clearly
- provide a map-oriented and analyst-friendly experience

## Extensibility points

- `ml.training.base.ForecasterModel`: swap model families without changing orchestration
- `backend.app.services.live_provider.LiveDataProvider`: add real APIs later
- artifact metadata registry: supports model versioning
- spatial features already exist for future graph/spatio-temporal models


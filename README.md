# Real-Time AI System for Monitoring and Short-Term Forecasting of Ground-Level O3 and NO2

A production-minded full-stack platform for Delhi site-level air quality monitoring, short-term forecasting, alerting, and model observability. The system is built around the provided SIH dataset, supports optional external air-quality augmentation, and separates historical training data, external live data, simulated fallback data, and forecast outputs so it behaves like a real operational stack rather than a notebook demo.

## What is implemented

- Configurable data ingestion and validation for the seven-site SIH dataset
- Temporal-safe feature engineering and train/validation/test splitting
- Two forecasting model families:
  - baseline multi-output random forest regressor
  - advanced PyTorch LSTM sequence forecaster
  - the backend defaults to the best-performing available artifact, which is currently the baseline profile
- Artifact persistence for preprocessors, metadata, metrics, and trained models
- FastAPI backend with structured logging, typed schemas, forecasting, trends, alerts, readiness checks, and both live replay and external live air-quality endpoints
- React + TypeScript dashboard with current status cards, temporal trends, historical/live/forecast comparison, map view, playback, and alert panels
- Groq-powered research copilot workspace with sign-in, persistent sessions, agent logs, structured reports, exports, follow-ups, and a lightweight knowledge graph
- Unit and smoke tests for the data pipeline and backend API
- Docker/dev setup and scripts for data preparation, external data sync, training, and one-command local stack startup

## Dataset-driven understanding

The provided ZIP contains seven Delhi sites with:

- `site_X_train_data.csv`: 16 columns, including two targets
- `site_X_unseen_input_data.csv`: 14 columns, the same exogenous inputs without targets
- `lat_lon_sites.txt`: site coordinates for all seven stations
- `Read_me.docx`: problem statement describing a 24-hour forecasting goal

Actual column schema observed in the CSV files:

- Temporal fields: `year`, `month`, `day`, `hour`
- Reanalysis/forecast features: `O3_forecast`, `NO2_forecast`, `T_forecast`, `q_forecast`, `u_forecast`, `v_forecast`, `w_forecast`
- Satellite features: `NO2_satellite`, `HCHO_satellite`, `ratio_satellite`
- Targets: `O3_target`, `NO2_target`

Important data properties:

- Data are hourly within each day, but days are shuffled in the raw training files.
- Satellite features are daily and extremely sparse in the supplied CSVs.
- Site coordinates are available and are used for visualization and extensibility.
- The README suggests using up to seven days of past target values; this implementation uses configurable lag windows and forecast horizons.

See [docs/data_dictionary.md](docs/data_dictionary.md) and [docs/architecture.md](docs/architecture.md) for the formal schema and system design.

## Repository layout

```text
air-quality-ai/
  backend/
    app/
    tests/
  ml/
    configs/
    data/
    features/
    training/
    inference/
    evaluation/
    artifacts/
  frontend/
    src/
  scripts/
  docs/
```

## Quick start

1. Create a Python virtual environment and install backend/ML dependencies:

```bash
pip install -e .[dev]
```

2. Install frontend dependencies:

```bash
cd frontend
npm install
```

3. Copy `.env.example` to `.env` and adjust paths if needed.

4. Prepare the dataset:

```bash
python scripts/prepare_data.py --source "C:\Users\Srishti Pandey\Downloads\SIH_Data_PS-10 (1).zip"
```

5. Optionally ingest external air-quality context for all sites:

```bash
python scripts/fetch_external_air_quality.py
```

6. Train models:

```bash
python scripts/train_models.py
```

To train with external auxiliary air-quality features as well:

```bash
python scripts/train_models.py --use-external-features
```

To build explicit named profiles:

```bash
python scripts/train_models.py --profile zip_only
python scripts/train_models.py --use-external-features --profile external_augmented
```

To activate one of the completed profiles as the default runtime:

```bash
python scripts/activate_profile.py --profile zip_only
python scripts/activate_profile.py --profile external_augmented
```

7. Start the backend:

```bash
uvicorn backend.app.main:app --reload
```

8. Start the frontend:

```bash
cd frontend
npm run dev
```

Or run the local stack together:

```bash
python scripts/run_local_stack.py
```

## Research copilot

The dashboard now includes a persistent research workspace tailored to this project:

- Groq generation model: `llama-3.3-70b-versatile`
- Embedding model target: `all-MiniLM-L6-v2`
- Session-based architecture with:
  - sign up / sign in / sign out
  - persistent sessions and restored history
  - agent logs for `search -> browse -> extract -> analyze -> summarize -> score -> final`
  - structured report sections, follow-ups, contradictions, source grounding, and confidence breakdown
  - JSON / Markdown / PDF export
  - lightweight user knowledge graph view

To enable Groq synthesis, set `GROQ_API_KEY` in `.env`.
If Groq is unavailable, the agent falls back to a deterministic structured-report mode instead of failing hard.

## Core workflows

### Training pipeline

- Raw site CSVs are consolidated into a typed, site-aware dataset.
- The pipeline reconstructs timestamps, sorts by `site_id` and `timestamp`, validates schema, imputes sparse fields, and builds lag-based and cyclical time features.
- Temporal train/validation/test splits use chronological boundaries to avoid random leakage.
- Both model families are trained against the same preprocessed features and evaluated with RMSE, MAE, R2, and RIA.
- Active runtime artifacts are stored in `ml/artifacts/`.
- Reproducible profile snapshots are stored in `ml/profiles/artifacts/` and `ml/profiles/processed/`.

### Serving pipeline

- Backend services load processed data and model metadata on startup.
- A live provider chain first tries the Open-Meteo external air-quality feed for live O3/NO2 conditions and falls back to cached external data or the replay simulator if needed.
- Forecast requests resolve the appropriate trained model and latest feature window, then return hourly predictions plus confidence bands derived from residual statistics.
- Alert logic compares live and forecast values against configurable pollutant thresholds.

### Frontend dashboard

- Pulls summary, live, trend, forecast, metadata, and alert endpoints from FastAPI
- Supports site switching, timeline scrubbing, auto-refresh, and map-based exploration
- Uses clear pollutant encoding:
  - O3: amber/orange
  - NO2: deep red
  - Forecast uncertainty: translucent confidence bands

## Configuration

Environment variables are documented in `.env.example`. The main knobs are:

- dataset paths
- model selection
- forecast horizon and lookback
- simulation cadence
- alert thresholds
- API/frontend origin settings

## Testing

Run:

```bash
pytest
```

Frontend lint/build commands are defined in `frontend/package.json`.

## Assumptions and extensions

- Because the supplied training CSVs are shuffled by day, the pipeline reconstructs true temporal order before any splitting or sequence generation.
- Satellite columns are kept but are imputed and flagged because missingness is dominant.
- The platform now supports a real external air-quality feed using the Open-Meteo Air Quality API for live conditions and optional auxiliary training features.
- External API data are used as exogenous context, not as the supervised ground-truth labels. The supervised targets remain the SIH `O3_target` and `NO2_target` columns because those are the provided labeled measurements.
- The architecture allows future additions such as graph/spatio-temporal neural models, Kafka ingestion, model registry integration, and scheduled retraining.

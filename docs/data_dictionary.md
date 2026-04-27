# Data Dictionary

## Source files

- `site_1_train_data.csv` to `site_7_train_data.csv`
- `site_1_unseen_input_data.csv` to `site_7_unseen_input_data.csv`
- `lat_lon_sites.txt`
- `Read_me.docx`

## Entity model

Each row represents one hourly observation for a given monitoring site in Delhi.

Canonical internal schema:

| Field | Type | Role | Notes |
|---|---|---|---|
| `site_id` | `int` | key | Parsed from file name and joined with site coordinates |
| `dataset_split` | `str` | lineage | `train` or `unseen` |
| `timestamp` | `datetime64[ns]` | temporal key | Reconstructed from `year`, `month`, `day`, `hour` |
| `year` | `int` | raw temporal | Preserved from source |
| `month` | `int` | raw temporal | Preserved from source |
| `day` | `int` | raw temporal | Preserved from source |
| `hour` | `int` | raw temporal | Preserved from source |
| `O3_forecast` | `float` | feature | Reanalysis/forecast input |
| `NO2_forecast` | `float` | feature | Reanalysis/forecast input |
| `T_forecast` | `float` | feature | Temperature-related exogenous driver |
| `q_forecast` | `float` | feature | Humidity or moisture-related exogenous driver |
| `u_forecast` | `float` | feature | Wind component |
| `v_forecast` | `float` | feature | Wind component |
| `w_forecast` | `float` | feature | Vertical wind component |
| `NO2_satellite` | `float` | sparse feature | Daily satellite observation, mostly missing |
| `HCHO_satellite` | `float` | sparse feature | Daily satellite observation, mostly missing |
| `ratio_satellite` | `float` | sparse feature | Derived ratio, mostly missing |
| `O3_target` | `float` | target | Ground-truth O3 concentration in ug m-3 |
| `NO2_target` | `float` | target | Ground-truth NO2 concentration in ug m-3 |
| `latitude` | `float` | spatial feature | Joined from `lat_lon_sites.txt` |
| `longitude` | `float` | spatial feature | Joined from `lat_lon_sites.txt` |
| `external_ozone` | `float` | optional external feature | Open-Meteo auxiliary O3 context when fetched |
| `external_nitrogen_dioxide` | `float` | optional external feature | Open-Meteo auxiliary NO2 context when fetched |
| `external_us_aqi` | `float` | optional external feature | Open-Meteo US AQI context |
| `external_european_aqi` | `float` | optional external feature | Open-Meteo European AQI context |

## Target columns

- `O3_target`
- `NO2_target`

## Temporal fields

- Raw temporal fields: `year`, `month`, `day`, `hour`
- Engineered temporal field: `timestamp`

Important finding:

- Rows are ordered by hour within a day but the training set is shuffled across days, so raw row order must never be used for temporal modeling.

## Candidate feature groups

### Direct exogenous inputs

- `O3_forecast`
- `NO2_forecast`
- `T_forecast`
- `q_forecast`
- `u_forecast`
- `v_forecast`
- `w_forecast`

### Sparse satellite inputs

- `NO2_satellite`
- `HCHO_satellite`
- `ratio_satellite`

These are retained with missingness indicators and imputation because they may still carry daily signal.

### Spatial context

- `site_id`
- `latitude`
- `longitude`

### External auxiliary context

- `external_ozone`
- `external_nitrogen_dioxide`
- `external_us_aqi`
- `external_european_aqi`

These are optional external exogenous features fetched from Open-Meteo and merged by site and timestamp when available.

### Time-derived features

- cyclical hour-of-day encoding
- cyclical day-of-year encoding
- weekend flag

### Lag and rolling features

- lagged `O3_target`
- lagged `NO2_target`
- lagged exogenous summaries
- rolling means and rolling standard deviations

## Data quality observations

- All numeric columns load as floats in the raw files.
- Satellite columns are overwhelmingly null across both train and unseen sets.
- Train files contain targets; unseen files do not.
- Site coordinates are available for all seven sites.

## Internal modeling assumptions

- Default forecast horizon: 24 hours
- Default lookback window: 168 hours (7 days)
- Temporal split strategy: site-wise chronological split after timestamp reconstruction
- Multi-target modeling: both pollutants forecasted jointly

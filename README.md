# Day-Ahead Electricity Price Forecasting

**SARIMA-GARCH and Quantile Gradient Boosting**  
Time Series Analysis (24AM7PCTSA) — Lab AAT

This project forecasts hourly German-Luxembourg (DE-LU) day-ahead electricity
prices. It compares a seasonal SARIMA point forecast with GARCH prediction
intervals against quantile gradient boosting point forecasts and intervals.
The report follows the supplied TSA AAT template.

## Run the project

Use Python 3.10 or later. From this folder:

```powershell
python -m pip install -r requirements.txt
python main.py
python -m streamlit run app.py
```

The hourly historical dataset is included, so the first run works offline.
`python main.py --refresh` downloads the same date range again from the public
API. It creates model results and charts in `outputs/` and an editable Word
report plus a PDF in `reports/`.

On Windows, you can instead double-click `run_dashboard.bat` to start the
dashboard. Keep the terminal window open while using the app, and open the
local URL it prints (normally <http://localhost:8501>). Closing the terminal
stops the app and makes its charts and downloads unavailable.

## Simple project demo

1. In VS Code, open this folder in the terminal.
2. Install the packages once with `python -m pip install -r requirements.txt`.
3. Run `python main.py`. This prepares the forecasts, charts, metrics, and report.
4. Start the dashboard with `python -m streamlit run app.py` (or double-click
   `run_dashboard.bat`). Keep the terminal open and use the local link it prints.
5. In “Forecast input: choose a test date (UTC),” select a date. The app shows
   that day's 24 hourly forecasts, prediction intervals, actual prices, and
   daily errors. This is a held-out historical test date: actual prices are
   included only to evaluate the already-made forecast.
6. Show the overall actual-versus-forecast chart, the two-model metric table,
   and the EDA chart. Set “Days shown in forecast chart” to the full test
   period shown in the sidebar (520 days for the included data).

The dashboard uses the included historical CSV; it has no data-upload form.
The test-date selector chooses which existing 24-hour forecast to inspect.
The sidebar slider only changes how many recent test days are visible in the
overview chart. Neither control retrains the models or changes the reported
full-test metrics. For a different test-window length, run
`python main.py --test-days 14` and then restart or refresh the dashboard.

If a previously open tab shows missing images or “Failed to fetch dynamically
imported module”, verify the server is still running, then hard-refresh the tab
with Ctrl+F5. This clears a cached Streamlit JavaScript bundle after a restart.
If the charts are still missing, run `python main.py` before starting the
dashboard to regenerate the forecast results and image files.

## Project contents

- `data/day_ahead_prices.csv` — hourly, UTC, DE-LU day-ahead prices.
- `src/forecasting.py` — data handling, leakage-safe features, models, and metrics.
- `main.py` — reproducible backtest and report-generation entry point.
- `app.py` — Streamlit dashboard for the data, model comparison, and forecasts.
- `reports/TSA_AAT_Report.pdf` — submission-ready report in the supplied section order.
- `reports/TSA_AAT_Report.docx` — editable copy of the report.
- `tests/` — fast checks for data validation and forecasting features.

## Data and method

Prices are obtained from the Energy-Charts price API for the DE-LU bidding
zone. The API attributes its data to Bundesnetzagentur / SMARD and provides it
under CC BY 4.0. Prices are EUR/MWh. Observations are stored in UTC; since
SMARD moved to 15-minute prices in October 2025, those observations are
averaged into hourly prices. The included series spans 2024-10-01 through
2026-08-31 UTC.

By default, the final maximum number of complete UTC test days is used while
retaining 180 days of initial training data. For the included 700-day dataset,
this gives 520 test dates, from 2025-03-30 to 2026-08-31; the earlier 180 days
are needed to train and initialize the models. Request a shorter evaluation
with `python main.py --test-days 30`. SARIMA uses a six-month training window
and is updated with actual observations only after each 24-hour forecast. A
GARCH(1,1) model estimates changing forecast uncertainty from SARIMA
residuals. The quantile gradient-boosting models estimate the 10th, 50th, and
90th percentiles using lagged prices, rolling statistics, and calendar
features. Their features use only prices available at least 24 hours before
each target.

MAE and RMSE evaluate point forecasts. sMAPE is reported instead of MAPE
because prices may be zero or negative. Interval coverage, mean interval
width, and quantile pinball loss assess uncertainty forecasts. The backtest
and report are generated from the local data, not from hand-entered results.

## Reproducibility and limitations

The included data keeps the dashboard and report generation independent of
network availability. Refreshing requires internet access. This is a
single-zone, price-only study: it does not use load, weather, generation,
cross-border flow, or fuel-price predictors. The UTC 24-hour horizon is not a
local-market calendar day across daylight-saving changes. The test period is
one chronological holdout from this single series, so results should not be
generalized to all seasons or bidding zones. Before submission, replace the
student, USN, section, signature, and team-contribution placeholders in the
report.

## Sources

- Data API: <https://api.energy-charts.info/> (DE-LU; CC BY 4.0 attribution to
  Bundesnetzagentur / SMARD).
- Weron, R. (2014). *Electricity price forecasting: A review of the
  state-of-the-art with a look into the future*. International Journal of
  Forecasting, 30(4), 1030–1081. <https://doi.org/10.1016/j.ijforecast.2014.08.008>
- Ziel, F. (2016). *Forecasting electricity spot prices using Lasso: On
  capturing the autoregressive intraday structure*. IEEE Transactions on Power
  Systems, 31(6), 4977–4987. <https://doi.org/10.1109/TPWRS.2016.2521545>
- Nowotarski, J., & Weron, R. (2018). *Recent advances in electricity price
  forecasting: A review of probabilistic forecasting*. Renewable and
  Sustainable Energy Reviews, 81, 1548–1568.
  <https://doi.org/10.1016/j.rser.2017.05.234>
- Uniejewski, B., Weron, R., & Ziel, F. (2018). *Variance stabilizing
  transformations for electricity spot price forecasting*. IEEE Transactions
  on Power Systems, 33(2), 2219–2229.
  <https://doi.org/10.1109/TPWRS.2017.2734563>
- Lago, J., Marcjasz, G., De Schutter, B., & Weron, R. (2021). *Forecasting day-ahead
  electricity prices: A review of state-of-the-art algorithms, best practices
  and an open-access benchmark*. Applied Energy, 293, 116983.
  <https://doi.org/10.1016/j.apenergy.2021.116983>
- García, R. C., Contreras, J., van Akkeren, M., & García, J. B. C. (2005).
  *A GARCH forecasting model to predict day-ahead electricity prices*. IEEE
  Transactions on Power Systems, 20(2), 867–874.
  <https://doi.org/10.1109/TPWRS.2005.846044>

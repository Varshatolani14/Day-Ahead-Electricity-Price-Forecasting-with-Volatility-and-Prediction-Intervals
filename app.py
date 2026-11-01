"""Streamlit dashboard for the reproducible day-ahead price backtest."""

from pathlib import Path
import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "day_ahead_prices.csv"
PREDICTIONS_PATH = ROOT / "outputs" / "backtest_predictions.csv"
METRICS_PATH = ROOT / "outputs" / "metrics.json"
CHART_PATHS = (ROOT / "outputs" / "eda.png", ROOT / "outputs" / "forecast_comparison.png")

st.set_page_config(page_title="Day-Ahead Price Forecasting", page_icon="⚡", layout="wide")
st.title("Day-Ahead Electricity Price Forecasting")
st.caption("SARIMA-GARCH baseline compared with Quantile Gradient Boosting | DE-LU market")

required_paths = (DATA_PATH, PREDICTIONS_PATH, METRICS_PATH, *CHART_PATHS)
if not all(path.exists() for path in required_paths):
    st.warning("Project results or chart images are missing. In the project folder, run `python main.py` first.")
    st.stop()

prices = pd.read_csv(DATA_PATH, parse_dates=["timestamp_utc"])
forecasts = pd.read_csv(PREDICTIONS_PATH, parse_dates=["timestamp_utc"]).set_index("timestamp_utc")
forecasts.index = pd.DatetimeIndex(pd.to_datetime(forecasts.index, utc=True))
metadata = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
model_metrics = metadata["metrics"]

st.sidebar.header("Display options")
test_days = int(metadata["test_days"])
forecast_dates = list(pd.DatetimeIndex(forecasts.index.normalize().unique()))
selected_date = st.sidebar.selectbox(
    "Forecast input: choose a test date (UTC)",
    options=forecast_dates,
    index=len(forecast_dates) - 1,
    format_func=lambda value: value.strftime("%Y-%m-%d"),
    help="Choose one held-out day to inspect its 24 hourly forecasts against the actual prices.",
)
days = st.sidebar.slider(
    "Days shown in forecast chart",
    min_value=1,
    max_value=test_days,
    value=min(7, test_days),
    help="This only changes the chart window. The models and full-test comparison metrics stay the same.",
)
st.sidebar.caption(f"Use {test_days} days to display the complete test forecast.")
recent = forecasts.iloc[-days * 24 :]
selected_day = forecasts.loc[forecasts.index.normalize() == selected_date]

columns = st.columns(4)
columns[0].metric("Test observations", f"{metadata['test_observations']:,}")
columns[1].metric("Test period", f"{metadata['test_days']} days")
columns[2].metric("Hourly prices", f"{len(prices):,}")
columns[3].metric("Market / unit", "DE-LU / EUR per MWh")

st.subheader("Forecasts and 80% prediction intervals")
fig, ax = plt.subplots(figsize=(12, 5), constrained_layout=True)
ax.plot(recent.index, recent["actual"], label="Actual", color="#222222", linewidth=1.6)
ax.plot(
    recent.index,
    recent["sarima_garch_forecast"],
    label="SARIMA-GARCH point forecast",
    color="#2367a5",
)
ax.fill_between(
    recent.index,
    recent["sarima_garch_lower"].to_numpy(),
    recent["sarima_garch_upper"].to_numpy(),
    color="#2367a5",
    alpha=0.15,
    label="SARIMA-GARCH interval",
)
ax.plot(recent.index, recent["qgb_forecast"], label="Quantile boosting median", color="#d46a22")
ax.fill_between(
    recent.index,
    recent["qgb_lower"].to_numpy(),
    recent["qgb_upper"].to_numpy(),
    color="#d46a22",
    alpha=0.16,
    label="Quantile boosting interval",
)
ax.set_ylabel("EUR/MWh")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.grid(alpha=0.25)
ax.legend(ncol=2)
st.pyplot(fig)
plt.close(fig)

st.subheader(f"Selected-day input and 24-hour forecast output: {selected_date:%Y-%m-%d} UTC")
st.caption(
    f"Input: the selected historical test date ({metadata['test_start'][:10]} to "
    f"{metadata['test_end'][:10]} UTC) and prices available before that day. "
    "Output: forecasts made before the day began; actual prices are shown only for evaluation."
)
selected_columns = {
    "actual": "Actual price (EUR/MWh)",
    "sarima_garch_forecast": "SARIMA-GARCH forecast",
    "sarima_garch_lower": "SARIMA lower 80%",
    "sarima_garch_upper": "SARIMA upper 80%",
    "qgb_forecast": "Quantile boosting forecast",
    "qgb_lower": "Quantile boosting lower 80%",
    "qgb_upper": "Quantile boosting upper 80%",
}
selected_results = selected_day[list(selected_columns)].rename(columns=selected_columns).round(2)
selected_metrics = st.columns(3)
selected_metrics[0].metric(
    "SARIMA-GARCH daily MAE",
    f"{(selected_day['actual'] - selected_day['sarima_garch_forecast']).abs().mean():.2f} EUR/MWh",
)
selected_metrics[1].metric(
    "Quantile boosting daily MAE",
    f"{(selected_day['actual'] - selected_day['qgb_forecast']).abs().mean():.2f} EUR/MWh",
)
selected_metrics[2].metric(
    "Quantile boosting interval coverage",
    f"{((selected_day['actual'] >= selected_day['qgb_lower']) & (selected_day['actual'] <= selected_day['qgb_upper'])).mean():.1%}",
)
st.table(selected_results)

st.subheader("Model comparison")
comparison = pd.DataFrame(model_metrics).T.rename(
    index={
        "sarima_garch": "SARIMA-GARCH",
        "quantile_boosting": "Quantile Gradient Boosting",
    }
)
comparison = comparison.rename(
    columns={
        "mae": "MAE (EUR/MWh)",
        "rmse": "RMSE (EUR/MWh)",
        "smape_percent": "sMAPE (%)",
        "coverage_80": "80% interval coverage",
        "mean_interval_width": "Mean interval width",
        "pinball_10": "10th percentile pinball loss",
        "pinball_90": "90th percentile pinball loss",
    }
)
st.table(comparison.style.format("{:.3f}"))
st.caption("sMAPE is used instead of MAPE because electricity prices can be zero or negative.")

st.subheader("Historical price patterns")
prices["timestamp_utc"] = pd.to_datetime(prices["timestamp_utc"], utc=True)
eda_col, details_col = st.columns([2, 1])
with eda_col:
    st.image(str(ROOT / "outputs" / "eda.png"), width="stretch")
with details_col:
    price_values = prices["price_eur_mwh"]
    st.metric("Mean price", f"{price_values.mean():.2f} EUR/MWh")
    st.metric("Median price", f"{price_values.median():.2f} EUR/MWh")
    st.metric("Minimum / maximum", f"{price_values.min():.2f} / {price_values.max():.2f}")
    st.write(f"Data period: {prices['timestamp_utc'].min().date()} to {prices['timestamp_utc'].max().date()} (UTC)")

st.subheader("Method")
st.write(
    "SARIMA models the conditional mean and GARCH(1,1) models changing residual variance. "
    "Three quantile gradient-boosting models estimate the 10th, 50th, and 90th percentiles "
    "from past prices and calendar features. Each test forecast uses a chronological "
    "24-hour horizon; actual prices enter the model history only after that day's forecast."
)
st.caption(
    "Data: Energy-Charts price API, DE-LU bidding zone; CC BY 4.0 attribution to "
    "Bundesnetzagentur / SMARD. Prices are EUR/MWh."
)

report_col, docx_col = st.columns(2)
pdf_path = ROOT / "reports" / "TSA_AAT_Report.pdf"
docx_path = ROOT / "reports" / "TSA_AAT_Report.docx"
if pdf_path.exists():
    report_col.download_button(
        "Download report (PDF)",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
    )
if docx_path.exists():
    docx_col.download_button(
        "Download editable report (DOCX)",
        data=docx_path.read_bytes(),
        file_name=docx_path.name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

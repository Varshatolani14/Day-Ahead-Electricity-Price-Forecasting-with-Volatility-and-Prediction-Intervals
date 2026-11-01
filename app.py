"""Interactive Streamlit dashboard for the day-ahead price backtest."""

import json
import math
import re
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st

from src.display import convert_price_values, price_conversion_factor

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "day_ahead_prices.csv"
PREDICTIONS_PATH = ROOT / "outputs" / "backtest_predictions.csv"
METRICS_PATH = ROOT / "outputs" / "metrics.json"
CURRENCIES_URL = "https://api.frankfurter.dev/v1/currencies"
RATES_URL = "https://api.frankfurter.dev/v1/latest?base=EUR"
FALLBACK_CURRENCIES = {
    "EUR": "Euro",
    "INR": "Indian Rupee",
    "USD": "United States Dollar",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
}
PRICE_COLUMNS = (
    "actual",
    "sarima_garch_forecast",
    "sarima_garch_lower",
    "sarima_garch_upper",
    "qgb_forecast",
    "qgb_lower",
    "qgb_upper",
)
MODEL_COLUMNS = {
    "SARIMA-GARCH": (
        "sarima_garch_forecast",
        "sarima_garch_lower",
        "sarima_garch_upper",
    ),
    "Quantile Gradient Boosting": ("qgb_forecast", "qgb_lower", "qgb_upper"),
}
MODEL_COLORS = {
    "SARIMA-GARCH": "#2367a5",
    "Quantile Gradient Boosting": "#d46a22",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_exchange_rates() -> tuple[dict[str, str], str, dict[str, float]]:
    """Fetch ECB reference rates through Frankfurter's public API."""
    currency_response = requests.get(CURRENCIES_URL, timeout=5)
    currency_response.raise_for_status()
    currencies = currency_response.json()
    rates_response = requests.get(RATES_URL, timeout=5)
    rates_response.raise_for_status()
    payload = rates_response.json()

    if not isinstance(currencies, dict) or not isinstance(payload, dict):
        raise ValueError("The exchange-rate service returned an unexpected response.")
    if payload.get("base") != "EUR" or not isinstance(payload.get("rates"), dict):
        raise ValueError("The exchange-rate service did not return EUR-based rates.")

    rates = {"EUR": 1.0}
    for code, value in payload["rates"].items():
        rate = float(value)
        if not re.fullmatch(r"[A-Z]{3}", code) or not math.isfinite(rate) or rate <= 0:
            raise ValueError("The exchange-rate service returned an invalid currency rate.")
        rates[code] = rate
    names = {"EUR": "Euro"}
    names.update({str(code): str(name) for code, name in currencies.items()})
    return names, str(payload["date"]), rates


st.set_page_config(
    page_title="Day-Ahead Electricity Price Forecasting",
    page_icon="⚡",
    layout="wide",
)

required_paths = (DATA_PATH, PREDICTIONS_PATH, METRICS_PATH)
if not all(path.exists() for path in required_paths):
    st.warning(
        "Project data or forecast results are missing. From the project folder, "
        "run `python main.py` first."
    )
    st.stop()

prices = pd.read_csv(DATA_PATH, parse_dates=["timestamp_utc"])
prices["timestamp_utc"] = pd.to_datetime(prices["timestamp_utc"], utc=True)
forecasts = pd.read_csv(PREDICTIONS_PATH, parse_dates=["timestamp_utc"]).set_index(
    "timestamp_utc"
)
forecasts.index = pd.DatetimeIndex(pd.to_datetime(forecasts.index, utc=True))
metadata = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
model_metrics = metadata["metrics"]
test_days = int(metadata["test_days"])
forecast_dates = list(pd.DatetimeIndex(forecasts.index.normalize().unique()))

with st.spinner("Loading current ECB reference rates..."):
    try:
        currency_names, rate_date, exchange_rates = fetch_exchange_rates()
        live_rates_available = True
        exchange_rate_error = ""
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        currency_names = FALLBACK_CURRENCIES
        rate_date = ""
        exchange_rates = {"EUR": 1.0}
        live_rates_available = False
        exchange_rate_error = str(error)

st.title("Day-Ahead Electricity Price Forecasting")
st.caption(
    "Explore hourly German–Luxembourg (DE-LU) prices, compare two forecast "
    "models, and inspect prediction intervals."
)

with st.sidebar:
    st.header("Explore the forecast")

    selected_date = st.selectbox(
        "Test date (UTC)",
        options=forecast_dates,
        index=len(forecast_dates) - 1,
        format_func=lambda value: value.strftime("%Y-%m-%d"),
        help=(
            "Choose a historical held-out test day. Dates outside this test set "
            "are not selectable because their actual outcomes are not evaluated."
        ),
    )
    chart_days = st.slider(
        "Forecast chart window (days)",
        min_value=1,
        max_value=test_days,
        value=min(7, test_days),
        help="Changes the visible chart window, not the models or full-test results.",
    )
    show_models = st.multiselect(
        "Forecasts to show",
        options=list(MODEL_COLUMNS),
        default=list(MODEL_COLUMNS),
    )
    show_actuals = st.checkbox("Show actual test prices", value=True)
    show_intervals = st.checkbox("Show nominal 80% intervals", value=True)
    chart_style = st.selectbox("Forecast line style", ["Line", "Step"])
    price_scale = st.selectbox(
        "Price-axis scale",
        ["Linear", "Symmetric log (spikes and negative prices)"],
    )

    st.divider()
    st.subheader("Currency and units")
    if not live_rates_available:
        st.warning(
            "Live exchange rates are unavailable. EUR is still available; use a "
            "manual positive rate for another currency. "
            f"Service detail: {exchange_rate_error}"
        )
    elif st.button("Refresh live exchange rates", use_container_width=True):
        fetch_exchange_rates.clear()
        st.rerun()

    currency_options = sorted(currency_names)
    currency_options.append("Other ISO currency code")
    default_currency = "INR" if live_rates_available and "INR" in currency_names else "EUR"
    initial_currency_index = currency_options.index(default_currency)
    selected_currency = st.selectbox(
        "Display currency",
        options=currency_options,
        index=initial_currency_index,
        format_func=lambda code: (
            f"{code} — {currency_names[code]}"
            if code in currency_names
            else code
        ),
        help="Live currencies are based on the latest published ECB reference rates.",
    )
    if selected_currency == "Other ISO currency code":
        currency_code = st.text_input(
            "Three-letter currency code",
            value="",
            max_chars=3,
            placeholder="e.g. INR",
        ).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency_code):
            st.error("Enter a valid three-letter ISO currency code.")
            st.stop()
    else:
        currency_code = selected_currency

    energy_unit = st.selectbox(
        "Energy unit",
        ["MWh", "kWh"],
        index=1 if currency_code == "INR" else 0,
    )
    if currency_code == "EUR":
        exchange_rate = 1.0
        rate_description = "original data currency"
    else:
        available_live_rate = exchange_rates.get(currency_code)
        rate_choices = (
            ["Latest ECB reference rate", "Enter a rate manually"]
            if available_live_rate is not None
            else ["Enter a rate manually"]
        )
        rate_source = st.radio("Exchange-rate source", rate_choices)
        if rate_source == "Latest ECB reference rate":
            exchange_rate = float(available_live_rate)
            rate_description = f"ECB reference rate via Frankfurter; as of {rate_date}"
        else:
            default_manual_rate = (
                float(available_live_rate) if available_live_rate is not None else 0.0
            )
            exchange_rate = st.number_input(
                f"Manual rate (1 EUR = {currency_code})",
                min_value=0.0,
                value=default_manual_rate,
                step=0.01,
                format="%.6f",
                help="Enter a current rate. It applies only to displayed/downloaded values.",
            )
            if exchange_rate <= 0:
                st.error("Enter a positive exchange rate to display this currency.")
                st.stop()
            rate_description = "user-entered rate"

    conversion_factor = price_conversion_factor(exchange_rate, energy_unit)
    st.caption(
        f"1 EUR = {exchange_rate:,.6g} {currency_code} ({rate_description})."
    )

    st.divider()
    st.subheader("Historical data options")
    history_days_max = max(1, len(prices) // 24)
    history_days = st.slider(
        "History window (days)",
        min_value=min(30, history_days_max),
        max_value=history_days_max,
        value=min(180, history_days_max),
    )
    historical_view = st.selectbox(
        "Historical view",
        ["Price over time", "Typical price by UTC hour", "Price distribution"],
    )
    aggregation = st.selectbox(
        "Time-series aggregation",
        ["Hourly", "Daily mean", "Weekly mean"],
        disabled=historical_view != "Price over time",
    )
    show_smoothing = st.checkbox(
        "Overlay rolling average",
        value=True,
        disabled=historical_view != "Price over time",
    )
    smoothing_points = st.slider(
        "Rolling-average window (points)",
        min_value=2,
        max_value=60,
        value=24 if aggregation == "Hourly" else 7,
        disabled=historical_view != "Price over time" or not show_smoothing,
    )

st.caption(
    f"Display conversion: prices start in EUR/MWh; charts, scorecards, and "
    f"forecast downloads use {currency_code}/{energy_unit}. "
    "INR is a converted DE-LU market price, not an Indian electricity-market quote. "
    "The source data, fitted models, and stored backtest results are unchanged."
)

overview = st.columns(4)
overview[0].metric("Held-out observations", f"{metadata['test_observations']:,}")
overview[1].metric("Test period", f"{metadata['test_days']} days")
overview[2].metric("Source observations", f"{len(prices):,}")
overview[3].metric("Market / display unit", f"DE-LU / {currency_code}/{energy_unit}")

forecast_tab, scorecard_tab, history_tab, methods_tab = st.tabs(
    ["Forecast explorer", "Model scorecard", "Historical explorer", "Method & downloads"]
)

with forecast_tab:
    recent = forecasts.iloc[-chart_days * 24 :].copy()
    recent_display = convert_price_values(recent.loc[:, PRICE_COLUMNS], exchange_rate, energy_unit)
    selected_day = forecasts.loc[forecasts.index.normalize() == selected_date].copy()
    selected_day_display = convert_price_values(
        selected_day.loc[:, PRICE_COLUMNS], exchange_rate, energy_unit
    )

    st.subheader("Day-ahead forecasts and prediction intervals")
    st.caption(
        f"Showing the most recent {chart_days} of {test_days} test days. "
        "Each forecast covers the next 24 UTC hours."
    )
    fig, ax = plt.subplots(figsize=(12, 4.8), constrained_layout=True)
    if show_actuals:
        ax.plot(
            recent_display.index,
            recent_display["actual"],
            label="Actual (evaluation only)",
            color="#222222",
            linewidth=1.6,
        )
    for model_name in show_models:
        forecast_column, lower_column, upper_column = MODEL_COLUMNS[model_name]
        color = MODEL_COLORS[model_name]
        if chart_style == "Step":
            ax.step(
                recent_display.index,
                recent_display[forecast_column],
                label=f"{model_name} forecast",
                color=color,
                where="post",
            )
        else:
            ax.plot(
                recent_display.index,
                recent_display[forecast_column],
                label=f"{model_name} forecast",
                color=color,
            )
        if show_intervals:
            ax.fill_between(
                recent_display.index,
                recent_display[lower_column].to_numpy(),
                recent_display[upper_column].to_numpy(),
                color=color,
                alpha=0.16,
                label=f"{model_name} 80% interval",
            )
    if not show_models:
        st.info("Select at least one forecast model in the sidebar to plot forecasts.")
    if historical_view != "Price distribution":
        ax.set_ylabel(f"{currency_code}/{energy_unit}")
    ax.set_xlabel("Delivery time (UTC)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(alpha=0.25)
    if price_scale == "Symmetric log (spikes and negative prices)":
        if historical_view == "Price distribution":
            ax.set_xscale("symlog", linthresh=max(conversion_factor * 10, 0.0001))
        else:
            ax.set_yscale("symlog", linthresh=max(conversion_factor * 10, 0.0001))
    if show_actuals or show_models:
        ax.legend(ncol=2)
    st.pyplot(fig, width="stretch")
    plt.close(fig)

    st.subheader(f"Selected test day: {selected_date:%Y-%m-%d} UTC")
    st.caption(
        f"Input: historical prices available before this day. Output: forecasts "
        "made before the day began. Actual values are included only to evaluate them."
    )
    selected_metrics = st.columns(max(len(show_models), 1))
    for position, model_name in enumerate(show_models):
        forecast_column, lower_column, upper_column = MODEL_COLUMNS[model_name]
        daily_mae = (
            selected_day["actual"] - selected_day[forecast_column]
        ).abs().mean() * conversion_factor
        coverage = (
            (selected_day["actual"] >= selected_day[lower_column])
            & (selected_day["actual"] <= selected_day[upper_column])
        ).mean()
        selected_metrics[position].metric(
            f"{model_name} daily MAE",
            f"{currency_code} {daily_mae:,.2f}/{energy_unit}",
        )
        selected_metrics[position].caption(f"80% interval coverage: {coverage:.1%}")

    selected_columns: dict[str, str] = {}
    if show_actuals:
        selected_columns["actual"] = f"Actual ({currency_code}/{energy_unit})"
    for model_name in show_models:
        forecast_column, lower_column, upper_column = MODEL_COLUMNS[model_name]
        selected_columns[forecast_column] = f"{model_name} forecast"
        if show_intervals:
            selected_columns[lower_column] = f"{model_name} lower 80%"
            selected_columns[upper_column] = f"{model_name} upper 80%"
    table_columns = list(selected_columns)
    if table_columns:
        selected_table = selected_day_display.loc[:, table_columns].rename(
            columns=selected_columns
        )
        selected_table.index.name = "Timestamp (UTC)"
        st.dataframe(
            selected_table.round(3),
            width="stretch",
            height=390,
        )
    else:
        st.info("Choose at least one forecast model or show actual prices to see the table.")

    selected_download = selected_day_display.rename(
        columns={
            "actual": f"actual_{currency_code}_per_{energy_unit}",
            "sarima_garch_forecast": f"sarima_garch_forecast_{currency_code}_per_{energy_unit}",
            "sarima_garch_lower": f"sarima_garch_lower_80_{currency_code}_per_{energy_unit}",
            "sarima_garch_upper": f"sarima_garch_upper_80_{currency_code}_per_{energy_unit}",
            "qgb_forecast": f"quantile_median_{currency_code}_per_{energy_unit}",
            "qgb_lower": f"quantile_lower_80_{currency_code}_per_{energy_unit}",
            "qgb_upper": f"quantile_upper_80_{currency_code}_per_{energy_unit}",
        }
    ).reset_index()
    st.download_button(
        "Download this day's converted forecasts (CSV)",
        data=selected_download.to_csv(index=False).encode("utf-8"),
        file_name=f"forecast_{selected_date:%Y-%m-%d}_{currency_code}_per_{energy_unit}.csv",
        mime="text/csv",
    )

with scorecard_tab:
    st.subheader("Full chronological test-period comparison")
    st.caption(
        "Both models use the same 520-day holdout. Currency and energy-unit "
        "selection changes price-valued metrics; percentages stay unchanged."
    )
    metric_names = {
        "Mean absolute error": "mae",
        "Root mean squared error": "rmse",
        "sMAPE (%)": "smape_percent",
        "80% interval coverage (%)": "coverage_80",
        "Mean interval width": "mean_interval_width",
        "10th-percentile pinball loss": "pinball_10",
        "90th-percentile pinball loss": "pinball_90",
    }
    chosen_metrics = st.multiselect(
        "Scorecard metrics",
        options=list(metric_names),
        default=list(metric_names),
    )
    comparison = pd.DataFrame(model_metrics).T.rename(
        index={
            "sarima_garch": "SARIMA-GARCH",
            "quantile_boosting": "Quantile Gradient Boosting",
        }
    )
    displayed_columns: dict[str, str] = {}
    for label in chosen_metrics:
        source_column = metric_names[label]
        if source_column == "smape_percent":
            comparison[label] = comparison[source_column]
        elif source_column == "coverage_80":
            comparison[label] = comparison[source_column] * 100
        else:
            comparison[label] = comparison[source_column] * conversion_factor
        displayed_columns[label] = label + (
            "" if source_column == "smape_percent" or source_column == "coverage_80"
            else f" ({currency_code}/{energy_unit})"
        )
    if chosen_metrics:
        comparison = comparison.loc[:, chosen_metrics].rename(
            columns=displayed_columns
        )
        st.dataframe(comparison.style.format("{:.3f}"), width="stretch")
    else:
        st.info("Select one or more metrics to display the scorecard.")
    st.caption(
        "MAE, RMSE, interval width, and pinball loss are lower-is-better. "
        "Coverage is best interpreted against the nominal 80% target. "
        "sMAPE is used instead of MAPE because prices may be zero or negative."
    )

    metric_to_column = {
        "MAE": "mae",
        "RMSE": "rmse",
        "sMAPE (%)": "smape_percent",
        "80% coverage (%)": "coverage_80",
        "Mean interval width": "mean_interval_width",
        "10th-percentile pinball": "pinball_10",
        "90th-percentile pinball": "pinball_90",
    }
    selected_metric = st.selectbox(
        "Plot one metric",
        options=list(metric_to_column),
    )
    column = metric_to_column[selected_metric]
    plotted_values = [
        model_metrics["sarima_garch"][column],
        model_metrics["quantile_boosting"][column],
    ]
    if column == "coverage_80":
        plotted_values = [value * 100 for value in plotted_values]
    elif column != "smape_percent":
        plotted_values = [value * conversion_factor for value in plotted_values]
    fig, ax = plt.subplots(figsize=(8, 3.2), constrained_layout=True)
    bars = ax.barh(
        ["SARIMA-GARCH", "Quantile Gradient Boosting"],
        plotted_values,
        color=[MODEL_COLORS["SARIMA-GARCH"], MODEL_COLORS["Quantile Gradient Boosting"]],
    )
    ax.set_title(selected_metric + (" (nominal target: 80%)" if column == "coverage_80" else ""))
    ax.set_xlabel(
        "%" if column in {"coverage_80", "smape_percent"} else f"{currency_code}/{energy_unit}"
    )
    ax.grid(axis="x", alpha=0.25)
    ax.set_axisbelow(True)
    for bar, value in zip(bars, plotted_values):
        ax.text(
            value,
            bar.get_y() + bar.get_height() / 2,
            f"  {value:.3f}",
            va="center",
        )
    st.pyplot(fig, width="stretch")
    plt.close(fig)

with history_tab:
    st.subheader("Explore historical price patterns")
    history_start = prices["timestamp_utc"].max() - pd.Timedelta(days=history_days)
    history = prices.loc[prices["timestamp_utc"] >= history_start].copy()
    history_series = history.set_index("timestamp_utc")["price_eur_mwh"]
    fig, ax = plt.subplots(figsize=(12, 4.8), constrained_layout=True)

    if historical_view == "Price over time":
        frequencies = {
            "Hourly": "h",
            "Daily mean": "D",
            "Weekly mean": "W",
        }
        historical_series = history_series.resample(
            frequencies[aggregation]
        ).mean().dropna()
        historical_display = convert_price_values(
            historical_series, exchange_rate, energy_unit
        )
        ax.plot(
            historical_display.index,
            historical_display,
            label=aggregation,
            linewidth=1.2,
            color="#2367a5",
        )
        if show_smoothing:
            rolling = historical_display.rolling(
                smoothing_points, min_periods=1
            ).mean()
            ax.plot(
                rolling.index,
                rolling,
                label=f"Rolling mean ({smoothing_points} points)",
                color="#d46a22",
                linewidth=2,
            )
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.set_xlabel("Timestamp (UTC)")
        ax.legend()
    elif historical_view == "Typical price by UTC hour":
        hourly = history.assign(hour=history["timestamp_utc"].dt.hour).groupby("hour")[
            "price_eur_mwh"
        ].median()
        hourly_display = convert_price_values(hourly, exchange_rate, energy_unit)
        ax.bar(hourly_display.index, hourly_display.values, color="#45a99b")
        ax.set_xticks(range(0, 24, 2))
        ax.set_xlabel("Hour of day (UTC)")
        ax.set_ylabel("Median price")
    else:
        distribution = convert_price_values(history_series, exchange_rate, energy_unit)
        ax.hist(distribution, bins=45, color="#45a99b", alpha=0.85)
        ax.axvline(distribution.median(), color="#ffa45b", linewidth=2, label="Median")
        ax.legend()
        ax.set_xlabel(f"Price ({currency_code}/{energy_unit})")
        ax.set_ylabel("Hourly observations")

    ax.set_ylabel(f"{currency_code}/{energy_unit}")
    if price_scale == "Symmetric log (spikes and negative prices)":
        ax.set_yscale("symlog", linthresh=max(conversion_factor * 10, 0.0001))
    ax.grid(axis="y", alpha=0.25)
    st.pyplot(fig, width="stretch")
    plt.close(fig)

    history_display = convert_price_values(
        history.loc[:, ["price_eur_mwh"]], exchange_rate, energy_unit
    ).rename(columns={"price_eur_mwh": f"price_{currency_code}_per_{energy_unit}"})
    history_download = history[["timestamp_utc"]].join(history_display)
    st.download_button(
        "Download visible historical window (CSV)",
        data=history_download.to_csv(index=False).encode("utf-8"),
        file_name=f"historical_prices_{history_days}d_{currency_code}_per_{energy_unit}.csv",
        mime="text/csv",
    )
    st.caption("Summary statistics below are calculated from the complete source dataset.")
    stats = convert_price_values(
        prices["price_eur_mwh"], exchange_rate, energy_unit
    )
    statistic_columns = st.columns(4)
    statistic_columns[0].metric("Mean", f"{currency_code} {stats.mean():,.2f}/{energy_unit}")
    statistic_columns[1].metric("Median", f"{currency_code} {stats.median():,.2f}/{energy_unit}")
    statistic_columns[2].metric("Minimum", f"{currency_code} {stats.min():,.2f}/{energy_unit}")
    statistic_columns[3].metric("Maximum", f"{currency_code} {stats.max():,.2f}/{energy_unit}")

with methods_tab:
    st.subheader("How the experiment works")
    st.write(
        "SARIMA(1,0,1) × (1,0,1,24) models the conditional mean; a GARCH(1,1) "
        "model estimates changing residual volatility. Three gradient-boosting "
        "models estimate the 10th, 50th, and 90th conditional price quantiles."
    )
    st.write(
        "The first 180 days initialize the models. Each forecast covers the next "
        "24 hours. The model history is updated with actual prices only after that "
        "day's forecast has been recorded. All displayed currency conversions "
        "happen after forecasting and do not retrain either model."
    )
    st.caption(
        "Data: Energy-Charts price API, DE-LU bidding zone; attributed to "
        "Bundesnetzagentur / SMARD under CC BY 4.0. Exchange rates: latest "
        "published ECB reference rates, retrieved through Frankfurter API. "
        "Rates are indicative, cached for one hour, and are not trading quotes."
    )
    st.subheader("Download project outputs")
    all_forecasts_display = convert_price_values(
        forecasts.loc[:, PRICE_COLUMNS], exchange_rate, energy_unit
    ).rename(
        columns={
            "actual": f"actual_{currency_code}_per_{energy_unit}",
            "sarima_garch_forecast": f"sarima_garch_forecast_{currency_code}_per_{energy_unit}",
            "sarima_garch_lower": f"sarima_garch_lower_80_{currency_code}_per_{energy_unit}",
            "sarima_garch_upper": f"sarima_garch_upper_80_{currency_code}_per_{energy_unit}",
            "qgb_forecast": f"quantile_median_{currency_code}_per_{energy_unit}",
            "qgb_lower": f"quantile_lower_80_{currency_code}_per_{energy_unit}",
            "qgb_upper": f"quantile_upper_80_{currency_code}_per_{energy_unit}",
        }
    ).reset_index()
    st.download_button(
        "Download all held-out forecasts (CSV)",
        data=all_forecasts_display.to_csv(index=False).encode("utf-8"),
        file_name=f"all_test_forecasts_{currency_code}_per_{energy_unit}.csv",
        mime="text/csv",
    )
    dataset_download = prices.copy()
    dataset_download["price_display"] = convert_price_values(
        dataset_download["price_eur_mwh"], exchange_rate, energy_unit
    )
    dataset_download[f"price_{currency_code}_per_{energy_unit}"] = (
        dataset_download.pop("price_display")
    )
    st.download_button(
        "Download source dataset with converted display column (CSV)",
        data=dataset_download.to_csv(index=False).encode("utf-8"),
        file_name=f"source_prices_{currency_code}_per_{energy_unit}.csv",
        mime="text/csv",
    )

    pdf_path = ROOT / "reports" / "TSA_AAT_Report.pdf"
    docx_path = ROOT / "reports" / "TSA_AAT_Report.docx"
    if pdf_path.exists():
        st.download_button(
            "Download AAT report (PDF)",
            data=pdf_path.read_bytes(),
            file_name=pdf_path.name,
            mime="application/pdf",
        )
    if docx_path.exists():
        st.download_button(
            "Download editable AAT report (DOCX)",
            data=docx_path.read_bytes(),
            file_name=docx_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

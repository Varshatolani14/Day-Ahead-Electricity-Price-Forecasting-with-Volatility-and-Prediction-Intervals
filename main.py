"""Run the electricity-price backtest and generate the AAT report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from reports.build_report import build_report
from src.forecasting import (
    DEFAULT_END,
    DEFAULT_START,
    download_prices,
    load_prices,
    maximum_test_days,
    run_backtest,
)

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "day_ahead_prices.csv"
OUTPUT_DIR = ROOT / "outputs"
REPORT_DIR = ROOT / "reports"


def create_charts(prices: pd.Series, forecasts: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    daily = prices.resample("D").mean()
    hourly_median = prices.groupby(prices.index.hour).median()
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    axes[0].plot(daily.index, daily, color="#1f5a94", linewidth=1)
    axes[0].set_title("Daily average day-ahead price")
    axes[0].set_ylabel("EUR/MWh")
    axes[0].grid(alpha=0.25)
    axes[1].plot(hourly_median.index, hourly_median.values, marker="o", color="#e07a2d")
    axes[1].set_title("Median price by UTC hour")
    axes[1].set_xlabel("Hour of day (UTC)")
    axes[1].set_ylabel("EUR/MWh")
    axes[1].set_xticks(range(0, 24, 2))
    axes[1].grid(alpha=0.25)
    fig.savefig(OUTPUT_DIR / "eda.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    recent = forecasts.iloc[-7 * 24 :]
    fig, ax = plt.subplots(figsize=(11, 4.5), constrained_layout=True)
    ax.plot(recent.index, recent["actual"], color="#222222", label="Actual", linewidth=1.5)
    ax.plot(
        recent.index,
        recent["sarima_garch_forecast"],
        color="#2367a5",
        label="SARIMA-GARCH point",
        linewidth=1,
    )
    ax.fill_between(
        recent.index,
        recent["sarima_garch_lower"].to_numpy(),
        recent["sarima_garch_upper"].to_numpy(),
        color="#2367a5",
        alpha=0.14,
        label="SARIMA-GARCH 80% interval",
    )
    ax.plot(
        recent.index,
        recent["qgb_forecast"],
        color="#d46a22",
        label="Quantile boosting median",
        linewidth=1,
    )
    ax.fill_between(
        recent.index,
        recent["qgb_lower"].to_numpy(),
        recent["qgb_upper"].to_numpy(),
        color="#d46a22",
        alpha=0.16,
        label="Quantile boosting 10-90% interval",
    )
    ax.set_title("Last seven days of the rolling day-ahead test")
    ax.set_ylabel("EUR/MWh")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(alpha=0.25)
    ax.legend(ncol=2, fontsize=8)
    fig.savefig(OUTPUT_DIR / "forecast_comparison.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the electricity price forecasting project.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download the historical data again from the Energy-Charts price API.",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=None,
        help="Number of final UTC days to test (defaults to the maximum, retaining 180 training days).",
    )
    args = parser.parse_args()
    if args.test_days is not None and args.test_days < 1:
        parser.error("--test-days must be a positive integer.")

    if args.refresh or not DATA_PATH.exists():
        print(f"Downloading DE-LU prices from {DEFAULT_START} to {DEFAULT_END}...")
        download_prices(DATA_PATH, start=DEFAULT_START, end=DEFAULT_END)

    prices = load_prices(DATA_PATH)
    print(f"Loaded {len(prices):,} hourly observations from {prices.index[0]} to {prices.index[-1]}.")
    if args.test_days is None:
        print(f"Using the maximum {maximum_test_days(prices)}-day test period with 180 training days.")
    forecasts, metadata = run_backtest(prices, test_days=args.test_days)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    forecasts.to_csv(OUTPUT_DIR / "backtest_predictions.csv", index_label="timestamp_utc")
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    create_charts(prices, forecasts)
    build_report(
        prices_path=DATA_PATH,
        forecasts_path=OUTPUT_DIR / "backtest_predictions.csv",
        metrics_path=OUTPUT_DIR / "metrics.json",
        output_dir=REPORT_DIR,
    )

    print("\nBacktest metrics:")
    for model, metrics in metadata["metrics"].items():
        print(
            f"{model:20} MAE={metrics['mae']:.2f}  RMSE={metrics['rmse']:.2f}  "
            f"80% coverage={metrics['coverage_80']:.1%}"
        )
    print(f"\nReport: {REPORT_DIR / 'TSA_AAT_Report.pdf'}")
    print(f"Editable report: {REPORT_DIR / 'TSA_AAT_Report.docx'}")


if __name__ == "__main__":
    main()

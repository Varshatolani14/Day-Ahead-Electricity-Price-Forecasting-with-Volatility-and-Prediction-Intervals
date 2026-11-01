"""Data preparation and day-ahead electricity-price forecasting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

DATA_URL = "https://api.energy-charts.info/price"
DEFAULT_START = "2024-10-01"
DEFAULT_END = "2026-09-01"
HOURS_PER_DAY = 24
MIN_TRAIN_DAYS = 180
SARIMA_TRAIN_DAYS = 180
FEATURE_COLUMNS = [
    "lag_24",
    "lag_48",
    "lag_168",
    "mean_24",
    "std_24",
    "mean_168",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
]


def download_prices(
    output_path: str | Path,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    bidding_zone: str = "DE-LU",
) -> pd.Series:
    """Download and hourly-average public day-ahead prices from SMARD."""
    response = requests.get(
        DATA_URL,
        params={"bzn": bidding_zone, "start": start, "end": end},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "unix_seconds" not in payload or "price" not in payload:
        raise ValueError("The price API response did not contain timestamps and prices.")
    if len(payload["unix_seconds"]) != len(payload["price"]):
        raise ValueError("The price API returned a different number of timestamps and prices.")

    raw = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(payload["unix_seconds"], unit="s", utc=True),
            "price": pd.to_numeric(payload["price"], errors="coerce"),
        }
    ).dropna(subset=["price"])
    start_utc = pd.Timestamp(start, tz="UTC")
    end_utc = pd.Timestamp(end, tz="UTC")
    raw = raw.loc[(raw["timestamp"] >= start_utc) & (raw["timestamp"] < end_utc)]
    if raw.empty:
        raise ValueError("The API returned no prices for the requested UTC date range.")

    # SMARD switched to 15-minute prices in October 2025; average them to hourly values.
    hourly = raw.set_index("timestamp")["price"].resample("h").mean()
    expected = pd.date_range(start_utc, end_utc, freq="h", inclusive="left")
    hourly = hourly.reindex(expected)
    if hourly.isna().any():
        hourly = hourly.interpolate(method="time", limit=2, limit_area="inside")
    if hourly.isna().any():
        gaps = int(hourly.isna().sum())
        raise ValueError(f"The downloaded series has {gaps} missing hourly price values.")
    hourly.index.name = "timestamp_utc"
    hourly.name = "price_eur_mwh"

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    hourly.rename_axis("timestamp_utc").reset_index().to_csv(path, index=False)
    return hourly


def load_prices(path: str | Path) -> pd.Series:
    """Load, validate, and return a regular hourly UTC price series."""
    frame = pd.read_csv(path, parse_dates=["timestamp_utc"])
    required = {"timestamp_utc", "price_eur_mwh"}
    if not required.issubset(frame.columns):
        raise ValueError(f"CSV must contain columns: {', '.join(sorted(required))}.")
    timestamps = pd.DatetimeIndex(pd.to_datetime(frame["timestamp_utc"], utc=True))
    values = pd.to_numeric(frame["price_eur_mwh"], errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=timestamps, name="price_eur_mwh")
    series = series.sort_index()
    if series.empty:
        raise ValueError("The price CSV is empty.")
    if series.index.has_duplicates:
        raise ValueError("The price CSV contains duplicate timestamps.")
    if not np.isfinite(series.to_numpy()).all():
        raise ValueError("The price CSV contains missing or non-finite prices.")
    if len(series) > 1 and not (series.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("The price CSV must contain consecutive hourly UTC observations.")
    return series


def _feature_row(history: pd.Series, target_time: pd.Timestamp) -> dict[str, float]:
    """Build features using observations available at least 24 hours before target."""
    def previous_window(hours_before: int, length: int) -> np.ndarray:
        end = target_time - pd.Timedelta(hours=hours_before)
        start = end - pd.Timedelta(hours=length - 1)
        window = history.loc[start:end].to_numpy(dtype=float)
        if len(window) != length:
            raise ValueError("Insufficient continuous history to create day-ahead features.")
        return window

    lag_times = [target_time - pd.Timedelta(hours=h) for h in (24, 48, 168)]
    if any(timestamp not in history.index for timestamp in lag_times):
        raise ValueError("Insufficient history for the 24-, 48-, and 168-hour lags.")

    hour = target_time.hour
    weekday = target_time.dayofweek
    month = target_time.month - 1
    window_24 = previous_window(24, 24)
    window_168 = previous_window(24, 168)
    return {
        "lag_24": float(history.loc[lag_times[0]]),
        "lag_48": float(history.loc[lag_times[1]]),
        "lag_168": float(history.loc[lag_times[2]]),
        "mean_24": float(window_24.mean()),
        "std_24": float(window_24.std()),
        "mean_168": float(window_168.mean()),
        "hour_sin": float(np.sin(2 * np.pi * hour / 24)),
        "hour_cos": float(np.cos(2 * np.pi * hour / 24)),
        "weekday_sin": float(np.sin(2 * np.pi * weekday / 7)),
        "weekday_cos": float(np.cos(2 * np.pi * weekday / 7)),
        "month_sin": float(np.sin(2 * np.pi * month / 12)),
        "month_cos": float(np.cos(2 * np.pi * month / 12)),
    }


def build_training_features(prices: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Create leakage-safe supervised features for a one-day-ahead forecast."""
    features = pd.DataFrame(index=prices.index)
    features["lag_24"] = prices.shift(24)
    features["lag_48"] = prices.shift(48)
    features["lag_168"] = prices.shift(168)
    available = prices.shift(24)
    features["mean_24"] = available.rolling(24).mean()
    features["std_24"] = available.rolling(24).std()
    features["mean_168"] = available.rolling(168).mean()
    hours = prices.index.hour
    weekdays = prices.index.dayofweek
    months = prices.index.month - 1
    features["hour_sin"] = np.sin(2 * np.pi * hours / 24)
    features["hour_cos"] = np.cos(2 * np.pi * hours / 24)
    features["weekday_sin"] = np.sin(2 * np.pi * weekdays / 7)
    features["weekday_cos"] = np.cos(2 * np.pi * weekdays / 7)
    features["month_sin"] = np.sin(2 * np.pi * months / 12)
    features["month_cos"] = np.cos(2 * np.pi * months / 12)
    valid = features.notna().all(axis=1)
    return features.loc[valid, FEATURE_COLUMNS], prices.loc[valid]


def maximum_test_days(prices: pd.Series) -> int:
    """Return the largest full-day holdout that preserves 180 training days."""
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("Prices must be sorted by unique timestamp.")
    if prices.index[0].hour != 0 or prices.index[-1].hour != 23 or len(prices) % HOURS_PER_DAY:
        raise ValueError("The hourly price series must start at 00:00 and end at 23:00 UTC.")
    available_days = len(prices) // HOURS_PER_DAY
    test_days = available_days - MIN_TRAIN_DAYS
    if test_days < 1:
        raise ValueError(f"At least {MIN_TRAIN_DAYS + 1} complete days of hourly prices are required.")
    return test_days


def _interval_metrics(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> dict[str, float]:
    return {
        "coverage_80": float(np.mean((actual >= lower) & (actual <= upper))),
        "mean_interval_width": float(np.mean(upper - lower)),
    }


def _pinball_loss(actual: np.ndarray, forecast: np.ndarray, quantile: float) -> float:
    error = actual - forecast
    return float(np.mean(np.maximum(quantile * error, (quantile - 1) * error)))


def evaluate_forecasts(
    actual: pd.Series,
    forecasts: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """Calculate point, interval, and quantile metrics for both models."""
    y = actual.to_numpy(dtype=float)
    results: dict[str, dict[str, float]] = {}
    for model, point_column, lower_column, upper_column in (
        ("sarima_garch", "sarima_garch_forecast", "sarima_garch_lower", "sarima_garch_upper"),
        ("quantile_boosting", "qgb_forecast", "qgb_lower", "qgb_upper"),
    ):
        point = forecasts[point_column].to_numpy(dtype=float)
        lower = forecasts[lower_column].to_numpy(dtype=float)
        upper = forecasts[upper_column].to_numpy(dtype=float)
        denominator = np.maximum((np.abs(y) + np.abs(point)) / 2, 1e-8)
        results[model] = {
            "mae": float(mean_absolute_error(y, point)),
            "rmse": float(np.sqrt(mean_squared_error(y, point))),
            "smape_percent": float(np.mean(2 * np.abs(y - point) / denominator) * 100),
            **_interval_metrics(y, lower, upper),
            "pinball_10": _pinball_loss(y, lower, 0.1),
            "pinball_90": _pinball_loss(y, upper, 0.9),
        }
    return results


def run_backtest(prices: pd.Series, test_days: int | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run a chronological, rolling 24-hour-ahead backtest."""
    from arch import arch_model
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    max_test_days = maximum_test_days(prices)
    if test_days is None:
        test_days = max_test_days
    if test_days < 1 or test_days > max_test_days:
        raise ValueError(
            f"test_days must be between 1 and {max_test_days} to retain "
            f"{MIN_TRAIN_DAYS} complete training days."
        )
    test_hours = test_days * HOURS_PER_DAY
    if prices.index[-test_hours].hour != 0:
        raise ValueError("The test period must start at 00:00 UTC for complete forecast days.")

    split_index = len(prices) - test_hours
    train = prices.iloc[:split_index]
    test = prices.iloc[split_index:]
    features_train, target_train = build_training_features(train)
    quantile_models: dict[float, GradientBoostingRegressor] = {}
    for quantile in (0.1, 0.5, 0.9):
        estimator = GradientBoostingRegressor(
            loss="quantile",
            alpha=quantile,
            n_estimators=150,
            learning_rate=0.05,
            max_depth=2,
            min_samples_leaf=15,
            subsample=0.8,
            random_state=42,
        )
        estimator.fit(features_train, target_train)
        quantile_models[quantile] = estimator

    # A recent six-month window keeps the seasonal state-space fit fast and responsive.
    sarima_train = train.iloc[-SARIMA_TRAIN_DAYS * HOURS_PER_DAY :].asfreq("h")
    sarima_model = SARIMAX(
        sarima_train,
        order=(1, 0, 1),
        seasonal_order=(1, 0, 1, 24),
        trend="c",
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    sarima_result = sarima_model.fit(disp=False, maxiter=80)
    sarima_converged = bool(sarima_result.mle_retvals.get("converged", False))
    residuals = np.asarray(sarima_result.resid, dtype=float)
    residuals = residuals[np.isfinite(residuals)]
    residual_scale = float(np.std(residuals, ddof=1))
    if residual_scale <= 0 or not np.isfinite(residual_scale):
        raise ValueError("SARIMA residuals do not have a usable variance for GARCH fitting.")
    normalized_residuals = residuals / residual_scale
    garch_result = arch_model(
        normalized_residuals,
        mean="Zero",
        vol="GARCH",
        p=1,
        q=1,
        rescale=False,
    ).fit(disp="off", show_warning=False)
    garch_parameters = garch_result.params
    omega = float(garch_parameters["omega"])
    alpha = float(garch_parameters["alpha[1]"])
    beta = float(garch_parameters["beta[1]"])
    next_variance = omega + alpha * normalized_residuals[-1] ** 2 + beta * float(
        garch_result.conditional_volatility[-1] ** 2
    )
    if not np.isfinite(next_variance) or next_variance <= 0:
        raise ValueError("The fitted GARCH model produced an invalid conditional variance.")

    records: list[dict[str, Any]] = []
    lower_quantile = 1.6448536269514722
    for day_start in range(0, test_hours, HOURS_PER_DAY):
        day_index = split_index + day_start
        day_actual = test.iloc[day_start : day_start + HOURS_PER_DAY]
        day_times = day_actual.index

        sarima_forecast = np.asarray(
            sarima_result.get_forecast(steps=HOURS_PER_DAY).predicted_mean,
            dtype=float,
        )
        variance = next_variance
        garch_variances: list[float] = []
        for _ in range(HOURS_PER_DAY):
            garch_variances.append(variance)
            variance = omega + (alpha + beta) * variance
        sarima_std = np.sqrt(np.asarray(garch_variances)) * residual_scale

        features_day = pd.DataFrame(
            [_feature_row(prices.iloc[:day_index], timestamp) for timestamp in day_times],
            index=day_times,
            columns=FEATURE_COLUMNS,
        )
        qgb_forecasts = np.column_stack(
            [quantile_models[q].predict(features_day) for q in (0.1, 0.5, 0.9)]
        )
        qgb_forecasts.sort(axis=1)
        if qgb_forecasts.shape != (HOURS_PER_DAY, 3):
            raise ValueError(f"Quantile models returned an unexpected forecast shape: {qgb_forecasts.shape}.")
        for hour_index, timestamp in enumerate(day_times):
            mean_value = float(sarima_forecast[hour_index])
            std_value = float(sarima_std[hour_index])
            q_lower, q_median, q_upper = (
                float(value) for value in qgb_forecasts[hour_index]
            )
            records.append(
                {
                    "timestamp_utc": timestamp,
                    "actual": float(day_actual.iloc[hour_index]),
                    "sarima_garch_forecast": mean_value,
                    "sarima_garch_lower": mean_value - lower_quantile * std_value,
                    "sarima_garch_upper": mean_value + lower_quantile * std_value,
                    "qgb_forecast": q_median,
                    "qgb_lower": q_lower,
                    "qgb_upper": q_upper,
                }
            )

        # Append observations only after producing the full 24-hour day-ahead forecast.
        sarima_result = sarima_result.extend(day_actual.asfreq("h"))
        new_residuals = np.asarray(sarima_result.resid, dtype=float)
        if not np.isfinite(new_residuals).all():
            raise ValueError("SARIMA produced non-finite residuals while updating the backtest.")
        for error in new_residuals / residual_scale:
            next_variance = omega + alpha * error**2 + beta * next_variance

    forecasts = pd.DataFrame.from_records(records).set_index("timestamp_utc")
    forecasts.index = pd.DatetimeIndex(forecasts.index, tz="UTC", name="timestamp_utc")
    metrics = evaluate_forecasts(test, forecasts)
    metadata = {
        "bidding_zone": "DE-LU",
        "frequency": "Hourly UTC; 15-minute API observations averaged to the hour",
        "training_start": train.index[0].isoformat(),
        "training_end": train.index[-1].isoformat(),
        "test_start": test.index[0].isoformat(),
        "test_end": test.index[-1].isoformat(),
        "training_observations": int(len(train)),
        "test_observations": int(len(test)),
        "test_days": int(test_days),
        "minimum_training_days": MIN_TRAIN_DAYS,
        "sarima_training_days": SARIMA_TRAIN_DAYS,
        "metrics": metrics,
        "sarima_converged": sarima_converged,
        "garch_converged": bool(garch_result.convergence_flag == 0),
        "sarima_parameters": "(1,0,1) x (1,0,1,24)",
        "garch_parameters": "GARCH(1,1), zero-mean standardized SARIMA residuals",
        "quantile_parameters": "GradientBoostingRegressor: 10th, 50th, and 90th percentiles",
    }
    return forecasts, metadata

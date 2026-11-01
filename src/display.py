"""Display-only transformations for forecast prices and price metrics."""

import math

import pandas as pd


def price_conversion_factor(exchange_rate: float, energy_unit: str) -> float:
    """Return the multiplier from EUR/MWh to the requested currency and unit."""
    if not math.isfinite(exchange_rate) or exchange_rate <= 0:
        raise ValueError("The EUR exchange rate must be a finite positive number.")
    if energy_unit == "MWh":
        return exchange_rate
    if energy_unit == "kWh":
        return exchange_rate / 1000
    raise ValueError("Energy unit must be 'MWh' or 'kWh'.")


def convert_price_values(
    values: pd.Series | pd.DataFrame,
    exchange_rate: float,
    energy_unit: str,
) -> pd.Series | pd.DataFrame:
    """Convert EUR/MWh values for display without changing stored forecasts."""
    return values * price_conversion_factor(exchange_rate, energy_unit)

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.forecasting import build_training_features, load_prices, maximum_test_days


class ForecastingDataTests(unittest.TestCase):
    def test_features_use_only_observations_at_least_one_day_old(self):
        index = pd.date_range("2025-01-01", periods=24 * 12, freq="h", tz="UTC")
        prices = pd.Series(np.arange(len(index), dtype=float), index=index)
        features, target = build_training_features(prices)
        target_time = index[24 * 8]
        self.assertEqual(features.loc[target_time, "lag_24"], prices.loc[target_time - pd.Timedelta(hours=24)])
        self.assertEqual(target.loc[target_time], prices.loc[target_time])
        self.assertNotIn(index[24 * 6], features.index)

    def test_csv_loader_rejects_non_hourly_data(self):
        frame = pd.DataFrame(
            {
                "timestamp_utc": ["2025-01-01T00:00:00Z", "2025-01-01T02:00:00Z"],
                "price_eur_mwh": [50.0, 55.0],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "consecutive hourly"):
                load_prices(path)

    def test_csv_loader_accepts_valid_hourly_data(self):
        frame = pd.DataFrame(
            {
                "timestamp_utc": ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"],
                "price_eur_mwh": [50.0, 55.0],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            frame.to_csv(path, index=False)
            series = load_prices(path)
        self.assertEqual(len(series), 2)
        self.assertEqual(str(series.index.tz), "UTC")

    def test_maximum_test_period_preserves_180_training_days(self):
        index = pd.date_range("2024-01-01", periods=24 * 700, freq="h", tz="UTC")
        prices = pd.Series(np.arange(len(index), dtype=float), index=index)
        self.assertEqual(maximum_test_days(prices), 520)

    def test_maximum_test_period_requires_complete_training_and_test_days(self):
        index = pd.date_range("2024-01-01", periods=24 * 180, freq="h", tz="UTC")
        prices = pd.Series(np.arange(len(index), dtype=float), index=index)
        with self.assertRaisesRegex(ValueError, "At least 181 complete days"):
            maximum_test_days(prices)


if __name__ == "__main__":
    unittest.main()

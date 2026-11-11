import numpy as np
import pandas as pd

from firegrowth import cumulative_area_growth, regression_metrics
from firegrowth.splits import temporal_split
from firegrowth.targets import dated_growth


def test_growth_uses_future_cumulative_union():
    result = cumulative_area_growth(np.array([10.0, 14.0, 20.0]), horizon_days=1)
    np.testing.assert_allclose(result[:2], [4.0, 6.0])
    assert np.isnan(result[2])


def test_metrics_are_signed_and_ignore_missing_pairs():
    result = regression_metrics(np.array([1.0, 2.0, np.nan]), np.array([2.0, 2.0, 99.0]))
    assert result["mae"] == 0.5
    assert result["bias"] == 0.5
    assert result["n"] == 2


def test_dated_growth_does_not_bridge_missing_calendar_days():
    frame = pd.DataFrame(
        {
            "observation_date": ["2025-01-01", "2025-01-03"],
            "cumulative_area_ha": [10.0, 30.0],
        }
    )
    assert dated_growth(frame, horizon_days=1).isna().all()


def test_temporal_split_excludes_groups_crossing_boundaries():
    frame = pd.DataFrame(
        {
            "event_id": ["cross", "cross", "train"],
            "reference_date": ["2025-09-30", "2025-10-01", "2025-01-01"],
            "target_end": ["2025-10-02", "2025-10-03", "2025-01-02"],
        }
    )
    result = temporal_split(frame)
    assert result["train"]["event_id"].tolist() == ["train"]
    assert result["excluded"]["event_id"].tolist() == ["cross", "cross"]

"""Divisões temporais com exclusão de episódios que atravessam fronteiras."""

from __future__ import annotations

import pandas as pd


def temporal_split(
    frame: pd.DataFrame,
    date_column: str = "reference_date",
    group_column: str = "event_id",
    target_end_column: str | None = "target_end",
    train_end: str = "2025-09-30",
    validation_end: str = "2025-12-31",
) -> dict[str, pd.DataFrame]:
    """Split complete groups into chronological train/validation/test sets.

    Groups crossing a partition boundary are returned in ``excluded`` rather
    than being split, preventing observations from one event appearing in more
    than one partition. If ``target_end_column`` exists, the future target must
    also finish before the partition boundary.
    """
    required = {date_column, group_column}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"missing columns: {sorted(missing)}")
    dates = pd.to_datetime(frame[date_column], utc=True)
    train_limit = pd.Timestamp(train_end, tz="UTC")
    validation_limit = pd.Timestamp(validation_end, tz="UTC")
    work = frame.copy()
    work["_reference"] = dates
    if target_end_column and target_end_column in work:
        work["_target_end"] = pd.to_datetime(work[target_end_column], utc=True)
    else:
        work["_target_end"] = work["_reference"]
    bounds = work.groupby(group_column, dropna=False).agg(
        first_reference=("_reference", "min"), last_target=("_target_end", "max")
    )
    labels = pd.Series("excluded", index=bounds.index, dtype="string")
    labels.loc[(bounds.last_target <= train_limit)] = "train"
    labels.loc[
        (bounds.first_reference > train_limit) & (bounds.last_target <= validation_limit)
    ] = "validation"
    labels.loc[bounds.first_reference > validation_limit] = "test"
    work["_partition"] = work[group_column].map(labels)
    result = {
        name: work.loc[work["_partition"] == name]
        .drop(columns=["_reference", "_target_end", "_partition"])
        .copy()
        for name in ("train", "validation", "test", "excluded")
    }
    return result

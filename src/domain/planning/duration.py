"""Estimativa determinística de duração para operações de manutenção."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, OrderedDict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from domain.planning.config import DurationConfig
from domain.planning.entities import DurationEstimate, HistoricalExecution, WorkOrderOperation
from domain.planning.enums import DurationSource

_SIMILARITY_CACHE_SIZE = 256


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must include a timezone")


def _round_minutes(value: float) -> int:
    """Round halves up and always retain the positive-minute contract."""

    return max(1, math.floor(value + 0.5))


def _percentile_nearest_rank(values: Sequence[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _median_from_sorted(values: Sequence[int]) -> float:
    midpoint = len(values) // 2
    if len(values) % 2:
        return float(values[midpoint])
    return (values[midpoint - 1] + values[midpoint]) / 2.0


def _normalized_title(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    tokens = re.findall(r"[a-z0-9]+", ascii_value.casefold())
    return " ".join(tokens)


def _title_similarity(left: str, right: str) -> float:
    normalized_left = _normalized_title(left)
    normalized_right = _normalized_title(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right, autojunk=False).ratio()


@dataclass(frozen=True, slots=True)
class _TitleFeatures:
    normalized: str
    counts: Counter[str]
    character_masks: dict[str, int]

    @property
    def length(self) -> int:
        return len(self.normalized)


def _features(value: str, cache: dict[str, _TitleFeatures]) -> _TitleFeatures:
    cached = cache.get(value)
    if cached is not None:
        return cached
    normalized = _normalized_title(value)
    character_masks: dict[str, int] = {}
    for position, character in enumerate(normalized):
        character_masks[character] = character_masks.get(character, 0) | (1 << position)
    result = _TitleFeatures(
        normalized=normalized,
        counts=Counter(normalized),
        character_masks=character_masks,
    )
    cache[value] = result
    return result


def _lcs_length(left: _TitleFeatures, right: _TitleFeatures) -> int:
    """Return exact LCS length using a bit-parallel dynamic program."""

    if left.length <= right.length:
        sequence = left.normalized
        masks = right.character_masks
    else:
        sequence = right.normalized
        masks = left.character_masks

    row = 0
    for character in sequence:
        matches = row | masks.get(character, 0)
        row = matches & ~(matches - ((row << 1) | 1))
    return row.bit_count()


def _similarity_at_least(
    left: _TitleFeatures,
    right: _TitleFeatures,
    threshold: float,
) -> bool:
    """Apply cheap, safe upper bounds before the exact SequenceMatcher ratio."""

    if not left.normalized or not right.normalized:
        return threshold <= 0.0
    if left.normalized == right.normalized:
        return True

    total_length = left.length + right.length
    # This is SequenceMatcher.real_quick_ratio(): no exact ratio can exceed it.
    length_upper_bound = 2.0 * min(left.length, right.length) / total_length
    if length_upper_bound < threshold:
        return False

    # This is SequenceMatcher.quick_ratio(), computed from cached character counts.
    # It is also an upper bound for ratio(), while avoiding rebuilding fullbcount.
    character_matches = sum(
        min(count, right.counts.get(character, 0))
        for character, count in left.counts.items()
    )
    character_upper_bound = 2.0 * character_matches / total_length
    if character_upper_bound < threshold:
        return False

    # SequenceMatcher's ordered matching blocks form a common subsequence. Their
    # total length therefore cannot exceed the exact LCS length. The bit-parallel
    # calculation is a much cheaper upper bound for unrelated maintenance titles.
    subsequence_upper_bound = 2.0 * _lcs_length(left, right) / total_length
    if subsequence_upper_bound < threshold:
        return False

    return (
        SequenceMatcher(
            None,
            left.normalized,
            right.normalized,
            autojunk=False,
        ).ratio()
        >= threshold
    )


@dataclass(slots=True)
class _HistoryIndex:
    executions: tuple[HistoricalExecution, ...]
    by_activity_asset: dict[tuple[str, str], tuple[HistoricalExecution, ...]]
    by_activity_location: dict[tuple[str, str], tuple[HistoricalExecution, ...]]
    by_asset: dict[str, tuple[HistoricalExecution, ...]]
    by_activity: dict[str, tuple[HistoricalExecution, ...]]
    by_location: dict[str, tuple[HistoricalExecution, ...]]
    by_title: dict[str, tuple[HistoricalExecution, ...]]
    title_features: dict[str, _TitleFeatures]
    normalization_cache: dict[str, _TitleFeatures]
    similarity_cache: OrderedDict[tuple[str, float], tuple[HistoricalExecution, ...]]

    @classmethod
    def build(
        cls,
        history: Iterable[HistoricalExecution],
        as_of: datetime,
        config: DurationConfig,
    ) -> _HistoryIndex:
        eligible = tuple(
            execution
            for execution in history
            if execution.finished_at <= as_of
            and 0 < execution.duration_minutes <= config.maximum_valid_minutes
        )
        activity_asset: dict[tuple[str, str], list[HistoricalExecution]] = {}
        activity_location: dict[tuple[str, str], list[HistoricalExecution]] = {}
        asset: dict[str, list[HistoricalExecution]] = {}
        activity: dict[str, list[HistoricalExecution]] = {}
        location: dict[str, list[HistoricalExecution]] = {}
        title: dict[str, list[HistoricalExecution]] = {}
        normalization_cache: dict[str, _TitleFeatures] = {}
        title_features: dict[str, _TitleFeatures] = {}

        for execution in eligible:
            if execution.activity_type_id is not None and execution.asset_id is not None:
                activity_asset.setdefault(
                    (execution.activity_type_id, execution.asset_id), []
                ).append(execution)
            if execution.activity_type_id is not None and execution.location_id is not None:
                activity_location.setdefault(
                    (execution.activity_type_id, execution.location_id), []
                ).append(execution)
            if execution.asset_id is not None:
                asset.setdefault(execution.asset_id, []).append(execution)
            if execution.activity_type_id is not None:
                activity.setdefault(execution.activity_type_id, []).append(execution)
            if execution.location_id is not None:
                location.setdefault(execution.location_id, []).append(execution)

            features = _features(execution.title, normalization_cache)
            title_features[features.normalized] = features
            title.setdefault(features.normalized, []).append(execution)

        return cls(
            executions=eligible,
            by_activity_asset={key: tuple(items) for key, items in activity_asset.items()},
            by_activity_location={
                key: tuple(items) for key, items in activity_location.items()
            },
            by_asset={key: tuple(items) for key, items in asset.items()},
            by_activity={key: tuple(items) for key, items in activity.items()},
            by_location={key: tuple(items) for key, items in location.items()},
            by_title={key: tuple(items) for key, items in title.items()},
            title_features=title_features,
            normalization_cache=normalization_cache,
            similarity_cache=OrderedDict(),
        )

    def similar_title(
        self,
        title: str,
        threshold: float,
    ) -> tuple[HistoricalExecution, ...]:
        target = _features(title, self.normalization_cache)
        cache_key = (target.normalized, threshold)
        cached = self.similarity_cache.get(cache_key)
        if cached is not None:
            self.similarity_cache.move_to_end(cache_key)
            return cached

        candidates: list[HistoricalExecution] = []
        for normalized, executions in self.by_title.items():
            if _similarity_at_least(target, self.title_features[normalized], threshold):
                candidates.extend(executions)
        result = tuple(candidates)
        self.similarity_cache[cache_key] = result
        if len(self.similarity_cache) > _SIMILARITY_CACHE_SIZE:
            self.similarity_cache.popitem(last=False)
        return result


def _exclude_current_operation(
    candidates: Sequence[HistoricalExecution],
    operation: WorkOrderOperation,
) -> tuple[HistoricalExecution, ...]:
    return tuple(
        execution
        for execution in candidates
        if not (
            execution.operation_id == operation.operation_id
            and execution.work_order_id == operation.work_order_id
        )
    )


def _historical_candidates(
    operation: WorkOrderOperation,
    index: _HistoryIndex,
    config: DurationConfig,
) -> Iterator[tuple[DurationSource, tuple[HistoricalExecution, ...]]]:
    activity_id = operation.activity_type_id
    asset_id = operation.asset_id
    location_id = operation.location_id

    yield (
        DurationSource.SAME_ACTIVITY_AND_ASSET,
        index.by_activity_asset.get((activity_id, asset_id), ())
        if activity_id is not None and asset_id is not None
        else (),
    )
    yield (
        DurationSource.SAME_ACTIVITY_AND_LOCATION,
        index.by_activity_location.get((activity_id, location_id), ())
        if activity_id is not None and location_id is not None
        else (),
    )
    yield (
        DurationSource.SAME_ASSET,
        index.by_asset.get(asset_id, ()) if asset_id is not None else (),
    )
    yield (
        DurationSource.SAME_ACTIVITY,
        index.by_activity.get(activity_id, ()) if activity_id is not None else (),
    )
    yield (
        DurationSource.SAME_LOCATION,
        index.by_location.get(location_id, ()) if location_id is not None else (),
    )
    yield (
        DurationSource.SIMILAR_TITLE,
        index.similar_title(operation.title, config.title_similarity_threshold),
    )
    yield (DurationSource.GLOBAL_MEDIAN, index.executions)


def _confidence(source: DurationSource, sample_size: int, minimum_sample_size: int) -> float:
    base = {
        DurationSource.SAME_ACTIVITY_AND_ASSET: 0.90,
        DurationSource.SAME_ACTIVITY_AND_LOCATION: 0.82,
        DurationSource.SAME_ASSET: 0.76,
        DurationSource.SAME_ACTIVITY: 0.74,
        DurationSource.SAME_LOCATION: 0.62,
        DurationSource.SIMILAR_TITLE: 0.56,
        DurationSource.GLOBAL_MEDIAN: 0.42,
    }[source]
    maturity = min(1.0, sample_size / max(minimum_sample_size * 3, 1))
    return round(min(0.95, base * (0.75 + 0.25 * maturity)), 6)


def _estimate_one(
    operation: WorkOrderOperation,
    history_index: _HistoryIndex,
    config: DurationConfig,
) -> DurationEstimate:
    planned = operation.planned_duration_minutes
    planned_is_valid = planned is not None and planned <= config.maximum_valid_minutes
    if config.prefer_planned and planned_is_valid:
        assert planned is not None
        return DurationEstimate(
            operation_id=operation.operation_id,
            minutes=planned,
            p50_minutes=planned,
            p80_minutes=planned,
            source=DurationSource.PLANNED,
            sample_size=0,
            confidence=1.0,
            reason_codes=("PLANNED_DURATION_USED",),
        )

    context_codes: list[str] = []
    if planned is not None and not planned_is_valid:
        context_codes.append("PLANNED_DURATION_INVALID")
    elif planned is None:
        context_codes.append("PLANNED_DURATION_MISSING")
    elif not config.prefer_planned:
        context_codes.append("PLANNED_DURATION_DISABLED")

    for source, indexed_candidates in _historical_candidates(
        operation,
        history_index,
        config,
    ):
        candidates = _exclude_current_operation(indexed_candidates, operation)
        if len(candidates) < config.minimum_sample_size:
            continue
        values = sorted(item.duration_minutes for item in candidates)
        p50 = _round_minutes(_median_from_sorted(values))
        p80_index = max(0, math.ceil(0.80 * len(values)) - 1)
        p80 = values[p80_index]
        return DurationEstimate(
            operation_id=operation.operation_id,
            minutes=p50,
            p50_minutes=p50,
            p80_minutes=max(p50, p80),
            source=source,
            sample_size=len(values),
            confidence=_confidence(source, len(values), config.minimum_sample_size),
            reason_codes=tuple(
                (*context_codes, "HISTORICAL_ESTIMATE", f"SOURCE_{source.value.upper()}")
            ),
        )

    if config.default_minutes is not None:
        return DurationEstimate(
            operation_id=operation.operation_id,
            minutes=config.default_minutes,
            p50_minutes=config.default_minutes,
            p80_minutes=config.default_minutes,
            source=DurationSource.DEFAULT,
            sample_size=0,
            confidence=0.20,
            reason_codes=tuple((*context_codes, "INSUFFICIENT_HISTORY", "DEFAULT_DURATION_USED")),
        )

    return DurationEstimate(
        operation_id=operation.operation_id,
        minutes=None,
        p50_minutes=None,
        p80_minutes=None,
        source=DurationSource.UNAVAILABLE,
        sample_size=0,
        confidence=0.0,
        reason_codes=tuple((*context_codes, "INSUFFICIENT_HISTORY", "DURATION_UNAVAILABLE")),
    )


def estimate_durations(
    operations: Iterable[WorkOrderOperation],
    history: Iterable[HistoricalExecution],
    as_of: datetime,
    config: DurationConfig,
) -> tuple[DurationEstimate, ...]:
    """Estimate duration for every operation without temporal leakage.

    History after ``as_of``, implausibly long records, and the target operation's
    own execution are ignored. Output follows input order because downstream joins
    use ``operation_id`` and callers may deliberately preserve backlog order.
    """

    _require_aware(as_of)
    history_snapshot = tuple(history)
    history_index = _HistoryIndex.build(history_snapshot, as_of, config)
    return tuple(
        _estimate_one(
            operation,
            history_index,
            config,
        )
        for operation in operations
    )

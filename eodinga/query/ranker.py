from __future__ import annotations

from collections.abc import Iterable, Mapping
import re

from pydantic import BaseModel, ConfigDict, Field

from eodinga.common import FileRecord


class RankingWeights(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: float = 0.6
    path: float = 0.25
    content: float = 0.15
    k: int = 60
    prefix_boost: float = 0.35
    deboost_factor: float = 0.4
    deboost_markers: tuple[str, ...] = Field(default=("node_modules", ".git"))


_PATH_SPLIT_RE = re.compile(r"[\\/]+")


def _path_has_marker_segment(path: str, marker: str) -> bool:
    return marker in _PATH_SPLIT_RE.split(path)


def reciprocal_rank_fusion(
    rank_sets: Mapping[str, Iterable[int]], weights: RankingWeights | None = None
) -> dict[int, float]:
    weights = weights or RankingWeights()
    score_map: dict[int, float] = {}
    channel_weights = {
        "name": weights.name,
        "path": weights.path,
        "content": weights.content,
    }
    for channel, ranking in rank_sets.items():
        channel_weight = channel_weights.get(channel, 0.0)
        for index, file_id in enumerate(ranking, start=1):
            score_map[file_id] = score_map.get(file_id, 0.0) + channel_weight / (weights.k + index)
    return score_map


def apply_prefix_boost(
    scores: Mapping[int, float],
    prefix_hits: Iterable[int],
    weights: RankingWeights | None = None,
) -> dict[int, float]:
    weights = weights or RankingWeights()
    boosted = dict(scores)
    for file_id in prefix_hits:
        boosted[file_id] = boosted.get(file_id, 0.0) + weights.prefix_boost
    return boosted


def apply_path_deboost(
    scores: Mapping[int, float],
    paths: Mapping[int, str],
    weights: RankingWeights | None = None,
) -> dict[int, float]:
    weights = weights or RankingWeights()
    adjusted = dict(scores)
    for file_id, path in paths.items():
        if any(_path_has_marker_segment(path, marker) for marker in weights.deboost_markers):
            adjusted[file_id] = adjusted.get(file_id, 0.0) * weights.deboost_factor
    return adjusted


def rank_results(
    name_hits: Iterable[int],
    path_hits: Iterable[int],
    content_hits: Iterable[int],
    prefix_hits: Iterable[int],
    paths: Mapping[int, str],
    weights: RankingWeights | None = None,
) -> dict[int, float]:
    weights = weights or RankingWeights()
    fused = reciprocal_rank_fusion(
        {"name": tuple(name_hits), "path": tuple(path_hits), "content": tuple(content_hits)},
        weights=weights,
    )
    boosted = apply_prefix_boost(fused, prefix_hits, weights=weights)
    return apply_path_deboost(boosted, paths, weights=weights)


def order_result_ids(scores: Mapping[int, float], records: Mapping[int, FileRecord]) -> list[int]:
    return sorted(
        scores,
        key=lambda file_id: (
            -scores[file_id],
            records[file_id].name_lower,
            str(records[file_id].path),
            file_id,
        ),
    )


__all__ = [
    "RankingWeights",
    "apply_path_deboost",
    "apply_prefix_boost",
    "order_result_ids",
    "rank_results",
    "reciprocal_rank_fusion",
]

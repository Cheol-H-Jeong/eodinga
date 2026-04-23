from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field


class RankingWeights(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: float = 0.6
    path: float = 0.25
    content: float = 0.15
    k: int = 60
    prefix_boost: float = 0.35
    deboost_factor: float = 0.4
    deboost_markers: tuple[str, ...] = Field(default=("node_modules", ".git"))


def _path_parts_lower(path: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in re.split(r"[\\/]+", path) if part)


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
    deboost_markers = {marker.casefold() for marker in weights.deboost_markers}
    for file_id, path in paths.items():
        if deboost_markers.intersection(_path_parts_lower(path)):
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


__all__ = [
    "RankingWeights",
    "apply_path_deboost",
    "apply_prefix_boost",
    "rank_results",
    "reciprocal_rank_fusion",
]

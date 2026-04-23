from __future__ import annotations

import pytest

from eodinga.query.ranker import (
    RankingWeights,
    apply_path_deboost,
    apply_prefix_boost,
    rank_results,
    reciprocal_rank_fusion,
)


def test_rrf_prefers_higher_weighted_channel() -> None:
    scores = reciprocal_rank_fusion({"name": [1, 2], "path": [2, 1], "content": []})
    assert scores[1] > scores[2]


def test_prefix_boost_increases_score() -> None:
    scores = apply_prefix_boost({1: 0.2, 2: 0.3}, [1], RankingWeights(prefix_boost=0.5))
    assert scores[1] == 0.7
    assert scores[2] == 0.3


def test_deboost_applies_to_vendor_dirs() -> None:
    scores = apply_path_deboost(
        {1: 1.0, 2: 1.0},
        {1: "/home/user/node_modules/pkg/index.js", 2: "/home/user/src/main.py"},
        RankingWeights(deboost_factor=0.25),
    )
    assert scores[1] == 0.25
    assert scores[2] == 1.0


def test_deboost_matches_complete_path_segments_only() -> None:
    scores = apply_path_deboost(
        {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0},
        {
            1: "/home/user/node_modules/pkg/index.js",
            2: "/home/user/node_modules_backup/pkg/index.js",
            3: r"C:\repo\.git\config",
            4: r"C:\repo\git-cache\config",
        },
        RankingWeights(deboost_factor=0.25),
    )

    assert scores[1] == 0.25
    assert scores[2] == 1.0
    assert scores[3] == 0.25
    assert scores[4] == 1.0


def test_rank_results_combines_rrf_boost_and_deboost() -> None:
    scores = rank_results(
        name_hits=[1, 2],
        path_hits=[2, 1],
        content_hits=[2],
        prefix_hits=[1],
        paths={1: "/repo/src/app.py", 2: "/repo/node_modules/app.js"},
    )
    assert scores[1] > scores[2]


def test_rrf_ignores_duplicate_ids_within_single_channel() -> None:
    weights = RankingWeights()

    scores = reciprocal_rank_fusion({"name": [1, 1, 2], "path": [], "content": []}, weights=weights)

    assert scores[1] == pytest.approx(weights.name / (weights.k + 1))
    assert scores[2] == pytest.approx(weights.name / (weights.k + 2))

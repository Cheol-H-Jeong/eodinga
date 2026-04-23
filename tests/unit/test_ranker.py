from __future__ import annotations

from pathlib import Path

from eodinga.common import FileRecord
from eodinga.query.ranker import (
    RankingWeights,
    apply_path_deboost,
    apply_prefix_boost,
    order_result_ids,
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


def test_order_result_ids_breaks_equal_scores_by_name_then_path() -> None:
    records = {
        10: FileRecord(
            id=10,
            root_id=1,
            path=Path("/repo/zeta/shared.txt"),
            parent_path=Path("/repo/zeta"),
            name="shared.txt",
            name_lower="shared.txt",
            ext="txt",
            size=1,
            mtime=1,
            ctime=1,
            is_dir=False,
            is_symlink=False,
            indexed_at=1,
        ),
        20: FileRecord(
            id=20,
            root_id=1,
            path=Path("/repo/alpha/shared.txt"),
            parent_path=Path("/repo/alpha"),
            name="shared.txt",
            name_lower="shared.txt",
            ext="txt",
            size=1,
            mtime=1,
            ctime=1,
            is_dir=False,
            is_symlink=False,
            indexed_at=1,
        ),
        30: FileRecord(
            id=30,
            root_id=1,
            path=Path("/repo/beta/alpha.txt"),
            parent_path=Path("/repo/beta"),
            name="alpha.txt",
            name_lower="alpha.txt",
            ext="txt",
            size=1,
            mtime=1,
            ctime=1,
            is_dir=False,
            is_symlink=False,
            indexed_at=1,
        ),
    }

    ordered = order_result_ids({10: 1.0, 20: 1.0, 30: 1.0}, records)

    assert ordered == [30, 20, 10]

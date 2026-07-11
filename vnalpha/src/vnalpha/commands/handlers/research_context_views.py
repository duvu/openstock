from __future__ import annotations

from collections.abc import Callable

from vnalpha.commands.models import ResultColumn, ResultPanel, ResultTable
from vnalpha.research_intelligence.models import SectorStrengthSnapshot

SnapshotFields = dict[str, str | int]
SnapshotPanelContent = SnapshotFields | dict[str, SnapshotFields]


def sector_table(snapshots: list[SectorStrengthSnapshot]) -> ResultTable:
    return ResultTable(
        title="Sector Strength",
        columns=[
            ResultColumn("rank", "Rank"),
            ResultColumn("sector", "Sector"),
            ResultColumn("score", "Score"),
            ResultColumn("return20", "Return 20D"),
            ResultColumn("rs20", "RS 20D"),
            ResultColumn("breadth_ma20", "Above MA20"),
            ResultColumn("breadth_ma50", "Above MA50"),
            ResultColumn("members", "Members"),
            ResultColumn("eligible", "Eligible"),
            ResultColumn("coverage", "Coverage"),
            ResultColumn("rotation", "Rotation"),
            ResultColumn("quality", "Quality"),
        ],
        rows=[
            [
                snapshot.rank,
                snapshot.sector,
                f"{snapshot.score:.3f}",
                percentage(snapshot.median_return20),
                percentage(snapshot.median_rs20_vs_vnindex),
                percentage(snapshot.pct_above_ma20),
                percentage(snapshot.pct_above_ma50),
                snapshot.member_count,
                snapshot.eligible_count,
                percentage(snapshot.metadata_coverage),
                snapshot.rotation,
                snapshot.quality,
            ]
            for snapshot in snapshots
        ],
    )


def sector_disclosure_panels(
    snapshots: list[SectorStrengthSnapshot],
) -> list[ResultPanel]:
    return [
        ResultPanel(
            title="Freshness",
            content=_snapshot_content(
                snapshots,
                lambda snapshot: {
                    "As of": snapshot.as_of_date.isoformat(),
                    "Freshness basis": snapshot.lineage.get("freshness_basis", "—"),
                    "Generated at": snapshot.generated_at.isoformat(),
                },
            ),
        ),
        ResultPanel(
            title="Lineage",
            content=_snapshot_content(
                snapshots, lambda snapshot: dict(snapshot.lineage)
            ),
        ),
        ResultPanel(
            title="Quality",
            content=_snapshot_content(
                snapshots,
                lambda snapshot: {
                    "Quality": snapshot.quality,
                    "Methodology": snapshot.methodology_version,
                    "Metadata coverage": percentage(snapshot.metadata_coverage),
                    "Unclassified": snapshot.unclassified_count,
                },
            ),
        ),
        caveat_panel(snapshot_warnings(snapshots)),
    ]


def caveat_panel(caveats: list[str] | tuple[str, ...]) -> ResultPanel:
    return ResultPanel(
        title="Data Caveats",
        content="\n".join(caveats) if caveats else "No persisted data caveats.",
    )


def snapshot_warnings(snapshots: list[SectorStrengthSnapshot]) -> list[str]:
    return [caveat for snapshot in snapshots for caveat in snapshot.caveats]


def percentage(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _snapshot_content(
    snapshots: list[SectorStrengthSnapshot],
    transform: Callable[[SectorStrengthSnapshot], SnapshotFields],
) -> SnapshotPanelContent:
    if len(snapshots) == 1:
        return transform(snapshots[0])
    return {snapshot.sector: transform(snapshot) for snapshot in snapshots}

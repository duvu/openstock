from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from vnalpha.data_availability.artifact_readiness import ArtifactReadinessService
from vnalpha.data_availability.artifact_readiness_models import (
    ArtifactReadinessRequest,
    ArtifactState,
    BoundedDateRange,
    ReadinessAction,
    ReadinessCapability,
)
from vnalpha.data_availability.policy import DataAvailabilityPolicy
from vnalpha.data_provisioning.source_policy import SourcePolicyResolver
from vnalpha.warehouse.migrations import run_migrations
from vnalpha.warehouse.write_coordinator import WarehouseWriteCoordinator


def _warehouse(directory: Path) -> Path:
    path = directory / "readiness.duckdb"
    with WarehouseWriteCoordinator(path=path).transaction() as connection:
        run_migrations(conn=connection, emit_observability=False)
    return path


def _dates(end_date: str, count: int = 120) -> list[str]:
    current = date.fromisoformat(end_date)
    values: list[str] = []
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current.isoformat())
        current -= timedelta(days=1)
    return list(reversed(values))


def _seed(
    connection: duckdb.DuckDBPyConnection,
    *,
    table: str,
    symbol: str,
    end_date: str,
    provider: str = "VCI",
    count: int = 120,
) -> None:
    values = _dates(end_date, count)
    if table == "canonical_ohlcv":
        statement = (
            "INSERT INTO canonical_ohlcv "
            "(symbol, time, interval, close, selected_provider, quality_status) "
            "VALUES (?, ?, '1D', 10.0, 'VCI', 'pass')"
        )
        connection.executemany(statement, [(symbol, value) for value in values])
        return
    statement = (
        "INSERT INTO market_ohlcv_raw "
        "(ingestion_run_id, symbol, time, interval, close, provider, quality_status) "
        "VALUES (?, ?, ?, '1D', 10.0, ?, 'pass')"
    )
    connection.executemany(
        statement,
        [(f"run-{value}", symbol, value, provider) for value in values],
    )


def _artifact(report, name: str):
    return next(artifact for artifact in report.artifacts if artifact.name == name)


def _request(capability: ReadinessCapability, *, historical: bool = False):
    return ArtifactReadinessRequest(
        symbol="VNM",
        effective_date="2024-09-30",
        capability=capability,
        historical=historical,
    )


def test_artifact_readiness_contract(tmp_path: Path, monkeypatch) -> None:
    ready_dir = tmp_path / "ready"
    ready_dir.mkdir()
    ready_path = _warehouse(ready_dir)
    with WarehouseWriteCoordinator(path=ready_path).transaction() as connection:
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('VNM')")
        _seed(connection, table="canonical_ohlcv", symbol="VNM", end_date="2024-09-30")
    with duckdb.connect(str(ready_path), read_only=True) as connection:
        before = connection.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[
            0
        ]
    price = ArtifactReadinessService(ready_path).inspect(
        _request(ReadinessCapability.PRICE_ANALYSIS)
    )
    with duckdb.connect(str(ready_path), read_only=True) as connection:
        after = connection.execute("SELECT COUNT(*) FROM canonical_ohlcv").fetchone()[0]
    assert price.requested_ready and not price.should_enqueue and before == after
    assert _artifact(price, "benchmark_ohlcv").required is False
    assert all(
        not artifact.actions for artifact in price.artifacts if not artifact.required
    )

    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    stale_path = _warehouse(stale_dir)
    with WarehouseWriteCoordinator(path=stale_path).transaction() as connection:
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('VNM')")
        _seed(connection, table="canonical_ohlcv", symbol="VNM", end_date="2024-09-27")
        _seed(
            connection,
            table="market_ohlcv_raw",
            symbol="VNM",
            end_date="2024-09-30",
            count=1,
        )
    stale = ArtifactReadinessService(stale_path).inspect(
        _request(ReadinessCapability.PRICE_ANALYSIS)
    )
    canonical = _artifact(stale, "canonical_ohlcv")
    assert canonical.state is ArtifactState.STALE and stale.should_enqueue
    assert [(action.action, action.date_range) for action in canonical.actions] == [
        (
            ReadinessAction.BUILD_TARGET_CANONICAL,
            BoundedDateRange("2024-09-30", "2024-09-30"),
        )
    ]

    weekend_dir = tmp_path / "weekend"
    weekend_dir.mkdir()
    weekend_path = _warehouse(weekend_dir)
    with WarehouseWriteCoordinator(path=weekend_path).transaction() as connection:
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('VNM')")
        _seed(connection, table="canonical_ohlcv", symbol="VNM", end_date="2024-09-26")
        _seed(connection, table="market_ohlcv_raw", symbol="VNM", end_date="2024-09-30")
        connection.execute(
            "DELETE FROM market_ohlcv_raw WHERE symbol = 'VNM' AND CAST(time AS DATE) = '2024-09-30'"
        )
        connection.execute(
            "INSERT INTO market_ohlcv_raw "
            "(ingestion_run_id, symbol, time, interval, close, provider, quality_status) "
            "VALUES ('weekend', 'VNM', '2024-09-28', '1D', 10.0, 'VCI', 'pass')"
        )
    weekend = ArtifactReadinessService(weekend_path).inspect(
        _request(ReadinessCapability.PRICE_ANALYSIS)
    )
    weekend_action = _artifact(weekend, "canonical_ohlcv").actions[0]
    assert weekend_action.action is ReadinessAction.SYNC_TARGET_OHLCV
    assert weekend_action.date_range == BoundedDateRange("2024-09-27", "2024-09-30")

    gap_dir = tmp_path / "gap"
    gap_dir.mkdir()
    gap_path = _warehouse(gap_dir)
    gap_date = _dates("2024-09-30")[60]
    with WarehouseWriteCoordinator(path=gap_path).transaction() as connection:
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('VNM')")
        _seed(
            connection,
            table="canonical_ohlcv",
            symbol="VNM",
            end_date="2024-09-30",
        )
        _seed(
            connection,
            table="market_ohlcv_raw",
            symbol="VNM",
            end_date="2024-09-30",
            count=121,
        )
        connection.execute(
            "DELETE FROM canonical_ohlcv WHERE symbol = 'VNM' AND CAST(time AS DATE) = ?",
            [gap_date],
        )
        connection.execute(
            "INSERT INTO canonical_ohlcv "
            "(symbol, time, interval, close, selected_provider, quality_status) "
            "VALUES ('VNM', '2023-08-08', '1D', 10.0, 'VCI', 'pass')"
        )
        connection.execute(
            "DELETE FROM market_ohlcv_raw WHERE symbol = 'VNM' AND CAST(time AS DATE) = ?",
            [gap_date],
        )
    gap = ArtifactReadinessService(gap_path).inspect(
        _request(ReadinessCapability.PRICE_ANALYSIS)
    )
    gap_artifact = _artifact(gap, "canonical_ohlcv")
    assert gap_artifact.state is ArtifactState.STALE
    assert [(action.action, action.date_range) for action in gap_artifact.actions] == [
        (ReadinessAction.SYNC_TARGET_OHLCV, BoundedDateRange(gap_date, gap_date))
    ]

    unapproved_dir = tmp_path / "unapproved"
    unapproved_dir.mkdir()
    unapproved_path = _warehouse(unapproved_dir)
    with WarehouseWriteCoordinator(path=unapproved_path).transaction() as connection:
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('VNM')")
        _seed(connection, table="canonical_ohlcv", symbol="VNM", end_date="2024-09-27")
        _seed(
            connection,
            table="market_ohlcv_raw",
            symbol="VNM",
            end_date="2024-09-30",
            provider="UNAPPROVED_PROVIDER",
        )
    unapproved = ArtifactReadinessService(unapproved_path).inspect(
        _request(ReadinessCapability.PRICE_ANALYSIS)
    )
    assert _artifact(unapproved, "canonical_ohlcv").actions[0].action is (
        ReadinessAction.SYNC_TARGET_OHLCV
    )
    explicit_source_blocked = ArtifactReadinessService(
        unapproved_path,
        policy=DataAvailabilityPolicy(source="fiinquantx"),
    ).inspect(_request(ReadinessCapability.PRICE_ANALYSIS))
    assert _artifact(explicit_source_blocked, "canonical_ohlcv").actions == ()
    assert not explicit_source_blocked.should_enqueue
    checks_only = ArtifactReadinessService(
        unapproved_path,
        policy=DataAvailabilityPolicy(auto_sync=False),
    ).inspect(_request(ReadinessCapability.PRICE_ANALYSIS))
    assert _artifact(checks_only, "canonical_ohlcv").actions == ()
    assert not checks_only.should_enqueue

    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    blocked_path = _warehouse(blocked_dir)
    with WarehouseWriteCoordinator(path=blocked_path).transaction() as connection:
        connection.execute("INSERT INTO symbol_master (symbol) VALUES ('VNM')")
        _seed(connection, table="canonical_ohlcv", symbol="VNM", end_date="2024-09-30")
    monkeypatch.delenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", raising=False)
    resolver = SourcePolicyResolver(configured_sources={"index.ohlcv": "fiinquantx"})
    ranking = ArtifactReadinessService(blocked_path, source_policy=resolver).inspect(
        _request(ReadinessCapability.CANDIDATE_RANKING)
    )
    historical = ArtifactReadinessService(blocked_path).inspect(
        _request(ReadinessCapability.CANDIDATE_RANKING, historical=True)
    )
    assert _artifact(ranking, "benchmark_ohlcv").repairable is False
    assert not ranking.should_enqueue
    assert ranking.effective_capability is ReadinessCapability.PRICE_ANALYSIS
    assert _artifact(historical, "benchmark_ohlcv").actions == ()
    assert not historical.should_enqueue

    with WarehouseWriteCoordinator(path=blocked_path).transaction() as connection:
        _seed(
            connection,
            table="canonical_ohlcv",
            symbol="VNINDEX",
            end_date="2024-09-30",
        )
    custom_benchmark = ArtifactReadinessService(
        blocked_path,
        policy=DataAvailabilityPolicy(benchmark="VN30"),
    ).inspect(_request(ReadinessCapability.CANDIDATE_RANKING))
    assert _artifact(custom_benchmark, "benchmark_ohlcv").state is ArtifactState.MISSING

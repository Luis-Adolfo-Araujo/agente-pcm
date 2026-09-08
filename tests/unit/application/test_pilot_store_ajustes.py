"""Persistência de ajustes manuais e restrições ao lado da run."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from application.pilot.store import SQLitePilotStore
from domain.planning.adjustments import AdjustmentKind, PlanningConstraints, ScheduleAdjustment
from tests.support.planning import run_base


def _store(tmp_path: Path) -> SQLitePilotStore:
    store = SQLitePilotStore(tmp_path / "pilot.sqlite3")
    store.initialize()
    return store


def _ajuste(seq: int) -> ScheduleAdjustment:
    return ScheduleAdjustment(
        sequence=seq, kind=AdjustmentKind.REMOVE, operation_id=f"op-{seq}",
        applied_by="ana", applied_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
    )


def test_adjustments_start_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    assert store.list_adjustments(run.run_id) == ()


def test_append_keeps_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.append_adjustment(run.run_id, _ajuste(1))
    ajustes = store.append_adjustment(run.run_id, _ajuste(2))
    assert [a.sequence for a in ajustes] == [1, 2]


def test_pop_last_removes_only_the_last(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.append_adjustment(run.run_id, _ajuste(1))
    store.append_adjustment(run.run_id, _ajuste(2))
    assert [a.sequence for a in store.pop_last_adjustment(run.run_id)] == [1]


def test_constraints_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.save_constraints(
        run.run_id, PlanningConstraints(must_include=("op-1",), blocked_days=(date(2026, 8, 21),))
    )
    guardadas = store.get_constraints(run.run_id)
    assert guardadas.must_include == ("op-1",)
    assert guardadas.blocked_days == (date(2026, 8, 21),)


def test_constraints_start_empty(tmp_path: Path) -> None:
    """Restrição nunca salva devolve vazio, não estoura."""
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    constraints = store.get_constraints(run.run_id)
    assert constraints.must_include == ()
    assert constraints.must_exclude == ()
    assert constraints.blocked_days == ()
    assert constraints.worker_asset_blocks == ()


def test_append_adjustment_ignores_client_sequence(tmp_path: Path) -> None:
    """A numeração é do servidor: o `sequence` do objeto recebido é ignorado."""
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    # Os dois ajustes chegam com sequence=1 (como um cliente ingênuo mandaria);
    # o servidor tem que renumerar em vez de gravar sequência duplicada.
    store.append_adjustment(run.run_id, _ajuste(1))
    ajustes = store.append_adjustment(run.run_id, _ajuste(1))
    assert [a.sequence for a in ajustes] == [1, 2]


def test_append_adjustment_round_trips_timezone(tmp_path: Path) -> None:
    """O JSON gravado sobrevive à ida e à volta com o fuso de `applied_at` intacto."""
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    store.append_adjustment(run.run_id, _ajuste(1))
    guardado = store.list_adjustments(run.run_id)[0]
    assert guardado.applied_at == datetime(2026, 8, 19, 12, tzinfo=UTC)
    assert guardado.applied_at.tzinfo is not None
    assert guardado.applied_at.utcoffset() == datetime(2026, 8, 19, 12, tzinfo=UTC).utcoffset()


def test_pop_last_removes_by_sequence_not_by_array_position(tmp_path: Path) -> None:
    """Remove o maior `sequence`, mesmo que o JSON grave os ajustes fora de ordem.

    `append_adjustment` nunca produziria essa desordem sozinho (a numeração é
    sempre crescente), mas o contrato de `pop_last_adjustment` é sobre
    `sequence`, não sobre a posição física do array — então escrevemos o JSON
    fora de ordem direto no banco para provar que a implementação não conta
    com as duas coisas coincidirem.
    """
    store = _store(tmp_path)
    run = run_base()
    store.create_run(run)
    fora_de_ordem = [
        _ajuste(2).model_dump(mode="json"),
        _ajuste(1).model_dump(mode="json"),
    ]
    with sqlite3.connect(tmp_path / "pilot.sqlite3") as connection:
        connection.execute(
            "UPDATE pilot_runs SET adjustments_json = ? WHERE run_id = ?",
            (json.dumps(fora_de_ordem), run.run_id),
        )
    remaining = store.pop_last_adjustment(run.run_id)
    assert [a.sequence for a in remaining] == [1]


_LEGACY_PILOT_RUNS_SCHEMA = """
    CREATE TABLE pilot_runs (
        run_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        request_json TEXT NOT NULL,
        config_json TEXT NOT NULL,
        proposal_id TEXT,
        summary_json TEXT,
        error TEXT,
        current_stage TEXT,
        trace_json TEXT NOT NULL DEFAULT '[]',
        artifact_names_json TEXT NOT NULL DEFAULT '[]'
    );
"""


def test_a_run_written_before_the_migration_survives_it(tmp_path: Path) -> None:
    """Uma run gravada sob o schema antigo continua legível depois do `ALTER TABLE`.

    Simula o schema de `pilot_runs` anterior à Tarefa 5 (sem `adjustments_json`
    nem `constraints_json`) e grava a run **nesse schema, antes de
    `initialize()` rodar pela primeira vez** — é o estado real de
    `var/pilot/pilot.sqlite3` no piloto: banco com runs, sem as colunas
    novas, até o primeiro boot depois desta tarefa. Só depois disso a
    migração roda (duas vezes, para cobrir também "banco já migrado, boot
    seguinte"), e a run tem que continuar legível, com ajustes e restrições
    vazios em vez de estourar.
    """
    db_path = tmp_path / "pilot.sqlite3"
    with sqlite3.connect(db_path) as legacy:
        legacy.executescript(_LEGACY_PILOT_RUNS_SCHEMA)

    # `create_run` só faz INSERT nas colunas que já existiam no schema
    # antigo, então grava direto sobre ele, sem `initialize()` ter rodado.
    legacy_store = SQLitePilotStore(db_path)
    run = run_base()
    legacy_store.create_run(run)

    migrated_store = SQLitePilotStore(db_path)
    migrated_store.initialize()
    migrated_store.initialize()

    recovered = migrated_store.get_run(run.run_id)
    assert recovered is not None
    assert recovered.run_id == run.run_id
    assert migrated_store.list_adjustments(run.run_id) == ()
    assert migrated_store.get_constraints(run.run_id) == PlanningConstraints()
    ajustes = migrated_store.append_adjustment(run.run_id, _ajuste(1))
    assert [a.sequence for a in ajustes] == [1]


def test_initialize_is_idempotent_on_an_existing_database(tmp_path: Path) -> None:
    """`initialize()` repetido sobre o mesmo arquivo não estoura `ALTER TABLE`.

    Complementa o teste acima: aqui o banco já nasce migrado (schema atual,
    com as duas colunas), e o que se verifica é que rodar `initialize()`
    várias vezes seguidas — como acontece a cada boot do piloto — nunca
    tenta acrescentar uma coluna que já existe.
    """
    db_path = tmp_path / "pilot.sqlite3"
    store = SQLitePilotStore(db_path)
    store.initialize()
    run = run_base()
    store.create_run(run)

    reopened = SQLitePilotStore(db_path)
    reopened.initialize()
    reopened.initialize()

    recovered = reopened.get_run(run.run_id)
    assert recovered is not None
    assert recovered.run_id == run.run_id
    assert reopened.list_adjustments(run.run_id) == ()
    ajustes = reopened.append_adjustment(run.run_id, _ajuste(1))
    assert [a.sequence for a in ajustes] == [1]

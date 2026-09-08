from datetime import date

from application.pilot.service import PilotService
from domain.planning.adjustments import AdjustmentKind

ServiceComRun = tuple[PilotService, str]


def test_revision_starts_at_zero(service_com_run: ServiceComRun) -> None:
    service, run_id = service_com_run
    revisao = service.get_revision(run_id)
    assert revisao["revision_sequence"] == 0
    assert revisao["adjustments"] == []
    assert revisao["created_violations"] == []


def test_adjustment_bumps_the_revision_and_reverifies(service_com_run: ServiceComRun) -> None:
    service, run_id = service_com_run
    alocada = service.get_schedule(run_id)["assignments"][0]
    revisao = service.add_adjustment(
        run_id, kind=AdjustmentKind.REMOVE, operation_id=alocada["operation_id"],
        target_date=None, target_worker_id=None, reason="parada de linha", applied_by="ana",
    )
    assert revisao["revision_sequence"] == 1
    assert any(
        u["operation_id"] == alocada["operation_id"] for u in revisao["solution"]["unscheduled"]
    )
    assert "verification" in revisao


def test_undo_returns_to_the_previous_revision(service_com_run: ServiceComRun) -> None:
    service, run_id = service_com_run
    alocada = service.get_schedule(run_id)["assignments"][0]
    service.add_adjustment(
        run_id, kind=AdjustmentKind.REMOVE, operation_id=alocada["operation_id"],
        target_date=None, target_worker_id=None, reason=None, applied_by="ana",
    )
    revisao = service.undo_last_adjustment(run_id)
    assert revisao["revision_sequence"] == 0
    assert any(
        a["operation_id"] == alocada["operation_id"] for a in revisao["solution"]["assignments"]
    )


def test_overloading_a_worker_creates_a_violation(service_com_run: ServiceComRun) -> None:
    service, run_id = service_com_run
    agenda = service.get_schedule(run_id)
    alvo = agenda["assignments"][0]
    dia = date.fromisoformat(alvo["window"]["start"][:10])
    revisao = service.add_adjustment(
        run_id, kind=AdjustmentKind.MOVE, operation_id=agenda["assignments"][-1]["operation_id"],
        target_date=dia, target_worker_id=alvo["worker_ids"][0], reason=None, applied_by="ana",
    )
    assert revisao["revision_sequence"] == 1
    assert isinstance(revisao["created_violations"], list)

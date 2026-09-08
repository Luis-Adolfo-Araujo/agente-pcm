"""Indicador de escala declarada acima do limite semanal."""

from datetime import UTC, datetime, timedelta

from application.pilot.models import CoverageIndicator, SnapshotQuality
from application.pilot.store import snapshot_quality
from domain.planning.entities import AvailabilitySlot, TimeWindow
from tests.support.planning import snapshot_base


def _slot(worker_id: str, dia: int, horas: float) -> AvailabilitySlot:
    inicio = datetime(2026, 8, dia, 6, tzinfo=UTC)
    return AvailabilitySlot(
        worker_id=worker_id,
        window=TimeWindow(start=inicio, end=inicio + timedelta(hours=horas)),
    )


def _indicador(quality: SnapshotQuality, chave: str) -> CoverageIndicator:
    return next(item for item in quality.indicators if item.key == chave)


def test_a_legal_weekly_scale_counts_as_present() -> None:
    # 3 dias de 12h15 é 12x36: 36,8h na semana, dentro do limite.
    slots = tuple(_slot("w-1", dia, 12.25) for dia in (18, 20, 22))
    snapshot = snapshot_base().model_copy(update={"availability": slots})
    indicador = _indicador(snapshot_quality(snapshot), "workers_within_weekly_hours")
    assert indicador.present == 1
    assert indicador.missing == 0


def test_a_scale_beyond_the_weekly_limit_is_flagged() -> None:
    # 7 dias de 12h15 é 85,8h na semana: escala que não existe.
    slots = tuple(_slot("w-1", dia, 12.25) for dia in range(18, 25))
    snapshot = snapshot_base().model_copy(update={"availability": slots})
    indicador = _indicador(snapshot_quality(snapshot), "workers_within_weekly_hours")
    assert indicador.present == 0
    assert indicador.missing == 1


def test_a_worker_without_any_scale_is_not_counted() -> None:
    # Ausência de escala já é denunciada por workers_with_availability; aqui ela
    # não pode virar "acima do limite", que é outra coisa.
    snapshot = snapshot_base().model_copy(update={"availability": ()})
    indicador = _indicador(snapshot_quality(snapshot), "workers_within_weekly_hours")
    assert indicador.total == 0

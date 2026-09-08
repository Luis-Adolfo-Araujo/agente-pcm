"""Snapshot fictício e determinístico para a demonstração pública.

Nada aqui vem de cliente. Ativos, ordens, técnicos, materiais e histórico saem
de uma semente, e a mesma semente devolve byte a byte o mesmo snapshot. A forma
segue o contrato canônico (`PlanningSnapshot`), então o arquivo gerado passa
pelo mesmo catálogo, pelas mesmas skills e pelo mesmo verificador que um
extrato real da origem.

O mundo é calibrado para caber apenas em parte na semana: o backlog pede mais
horas do que os técnicos têm, algumas ordens estão bloqueadas por dependência e
algumas pedem item sem saldo. A proposta então exibe as quatro saídas que o PCM
precisa distinguir — programada, sem capacidade, bloqueada e sem material —, em
vez de uma semana artificialmente folgada onde tudo entra.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from domain.planning.entities import (
    AvailabilitySlot,
    HistoricalExecution,
    InventoryPosition,
    MaterialRequirement,
    PlanningSnapshot,
    TimeWindow,
    WorkerProfile,
    WorkOrderOperation,
)

#: Fuso da planta fictícia. Deslocamento fixo para não depender da base IANA.
PLANT_TIMEZONE = timezone(timedelta(hours=-3))

DEFAULT_SEED = 20260817
DEFAULT_TENANT_ID = "demo-planta-modelo"
DEFAULT_OPERATION_COUNT = 1200
DEFAULT_INVENTORY_ITEMS = 1800


@dataclass(frozen=True, slots=True)
class _Family:
    """Uma família de ativos: quem atende, quanto costuma durar, quanto dói parar."""

    key: str
    label: str
    team: str
    base_minutes: int
    criticality: int
    asset_count: int
    activities: tuple[str, ...]


_FAMILIES: tuple[_Family, ...] = (
    _Family("compressor", "Compressor de ar", "mecanica", 180, 88, 4,
            ("preventiva", "corretiva", "lubrificacao")),
    _Family("bomba", "Bomba centrífuga", "mecanica", 90, 64, 12,
            ("preventiva", "corretiva", "lubrificacao")),
    _Family("esteira", "Esteira transportadora", "mecanica", 120, 58, 9,
            ("preventiva", "corretiva", "lubrificacao")),
    _Family("redutor", "Redutor", "mecanica", 150, 72, 8,
            ("preventiva", "corretiva", "lubrificacao")),
    _Family("talha", "Talha elétrica", "mecanica", 45, 26, 6,
            ("preventiva", "corretiva")),
    _Family("motor", "Motor elétrico", "eletrica", 100, 66, 14,
            ("preventiva", "corretiva", "termografia")),
    _Family("painel", "Painel de comando", "eletrica", 75, 52, 7,
            ("preventiva", "corretiva", "termografia")),
    _Family("inversor", "Inversor de frequência", "eletrica", 60, 44, 6,
            ("preventiva", "corretiva")),
    _Family("transmissor", "Transmissor de pressão", "instrumentacao", 45, 38, 10,
            ("preventiva", "corretiva", "calibracao")),
    _Family("valvula", "Válvula de controle", "instrumentacao", 90, 61, 11,
            ("preventiva", "corretiva", "calibracao")),
    _Family("analisador", "Analisador de gás", "instrumentacao", 120, 34, 4,
            ("preventiva", "calibracao")),
    _Family("lubrificador", "Sistema de lubrificação", "lubrificacao", 60, 29, 5,
            ("preventiva", "lubrificacao")),
)

#: Rótulo e fator de duração de cada tipo de atividade.
_ACTIVITIES: dict[str, tuple[str, float]] = {
    "preventiva": ("Inspeção preventiva", 1.0),
    "corretiva": ("Reparo corretivo", 1.6),
    "lubrificacao": ("Lubrificação programada", 0.5),
    "calibracao": ("Calibração", 0.8),
    "termografia": ("Termografia", 0.45),
}

_AREAS: tuple[str, ...] = (
    "utilidades",
    "linha-1",
    "linha-2",
    "expedicao",
    "tratamento-agua",
)

#: Quantos técnicos cada equipe tem. Total de 22, como uma planta média.
_TEAM_SIZE: dict[str, int] = {
    "mecanica": 9,
    "eletrica": 6,
    "instrumentacao": 5,
    "lubrificacao": 2,
}

#: Turnos em hora local. Dois blocos por dia deixam o intervalo de refeição
#: visível para o otimizador, que precisa de janela contígua.
_SHIFTS: dict[str, tuple[tuple[int, int], ...]] = {
    "manha": ((6, 11), (12, 15)),
    "tarde": ((14, 19), (20, 23)),
}

_BLOCK_REASONS: tuple[str, ...] = (
    "aguarda liberação da produção",
    "depende de parada de linha",
    "aguarda laudo de inspeção",
    "depende de outra ordem ainda aberta",
)


@dataclass(frozen=True, slots=True)
class _Asset:
    asset_id: str
    family: _Family
    label: str
    location_id: str


@dataclass(frozen=True, slots=True)
class _Worker:
    worker_id: str
    team: str
    shift: str
    day_off: int | None
    weekly_hours_overflow: bool


def _local(day: datetime, hour: int) -> datetime:
    return day.replace(hour=hour, minute=0, second=0, microsecond=0)


def _monday_of_week(reference: datetime) -> datetime:
    local = reference.astimezone(PLANT_TIMEZONE)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(days=(7 - midnight.weekday()) % 7 or 7)


def _build_assets() -> tuple[_Asset, ...]:
    assets: list[_Asset] = []
    counter = 0
    for family in _FAMILIES:
        for index in range(1, family.asset_count + 1):
            counter += 1
            assets.append(
                _Asset(
                    asset_id=f"asset-{counter:03d}",
                    family=family,
                    label=f"{family.label} {index:02d}",
                    location_id=f"area-{_AREAS[counter % len(_AREAS)]}",
                )
            )
    return tuple(assets)


def _build_workers(rng: random.Random) -> tuple[_Worker, ...]:
    workers: list[_Worker] = []
    counter = 0
    for team in sorted(_TEAM_SIZE):
        for _ in range(_TEAM_SIZE[team]):
            counter += 1
            shift = "tarde" if counter % 4 == 0 else "manha"
            # Uma folga na semana para parte da equipe, como numa escala real.
            day_off = rng.choice([None, None, None, 2, 4])
            workers.append(
                _Worker(
                    worker_id=f"tecnico-{counter:02d}",
                    team=team,
                    shift=shift,
                    day_off=day_off,
                    weekly_hours_overflow=False,
                )
            )
    # Um cadastro declara jornada acima do limite semanal. O indicador de
    # qualidade existe para expor isso; a demonstração não esconde o caso.
    workers[-1] = _Worker(
        worker_id=workers[-1].worker_id,
        team=workers[-1].team,
        shift=workers[-1].shift,
        day_off=None,
        weekly_hours_overflow=True,
    )
    return tuple(workers)


def _availability(workers: Sequence[_Worker], week_start: datetime) -> tuple[AvailabilitySlot, ...]:
    slots: list[AvailabilitySlot] = []
    for worker in workers:
        blocks = _SHIFTS[worker.shift]
        for weekday in range(5):
            if worker.day_off == weekday:
                continue
            day = week_start + timedelta(days=weekday)
            for start_hour, end_hour in blocks:
                start = _local(day, start_hour)
                end = _local(day, end_hour)
                if worker.weekly_hours_overflow:
                    end = end + timedelta(minutes=48)
                slots.append(
                    AvailabilitySlot(
                        worker_id=worker.worker_id,
                        window=TimeWindow(start=start, end=end),
                    )
                )
    return tuple(slots)


def _sample_duration(rng: random.Random, base: float) -> int:
    """Duração com cauda à direita: manutenção atrasa mais do que adianta."""

    factor = rng.lognormvariate(0.0, 0.28)
    return max(15, min(1440, int(round(base * factor / 5.0)) * 5))


def _build_history(
    rng: random.Random,
    assets: Sequence[_Asset],
    workers: Sequence[_Worker],
    as_of: datetime,
) -> tuple[HistoricalExecution, ...]:
    by_team: dict[str, list[_Worker]] = {}
    for worker in workers:
        by_team.setdefault(worker.team, []).append(worker)

    history: list[HistoricalExecution] = []
    counter = 0
    for asset in assets:
        team_workers = by_team[asset.family.team]
        # Cada ativo tem uma dupla recorrente: é dela que sai a afinidade que a
        # skill de executantes pontua.
        regulars = rng.sample(team_workers, k=min(3, len(team_workers)))
        for activity in asset.family.activities:
            label, factor = _ACTIVITIES[activity]
            base = asset.family.base_minutes * factor
            # Acima do tamanho mínimo de amostra, senão a estimativa cai no
            # padrão e o histórico não serve para nada.
            for _ in range(rng.randint(4, 7)):
                counter += 1
                finished_at = as_of - timedelta(
                    days=rng.randint(7, 180),
                    minutes=rng.randrange(0, 8 * 60, 5),
                )
                duration = _sample_duration(rng, base)
                crew = rng.sample(regulars, k=1 if rng.random() < 0.82 else 2)
                history.append(
                    HistoricalExecution(
                        work_order_id=f"wo-hist-{counter:05d}",
                        operation_id=f"op-hist-{counter:05d}",
                        title=f"{label} — {asset.family.label}",
                        finished_at=finished_at,
                        duration_minutes=duration,
                        labor_minutes=duration * len(crew),
                        worker_ids=tuple(item.worker_id for item in crew),
                        asset_id=asset.asset_id,
                        location_id=asset.location_id,
                        activity_type_id=f"atividade-{activity}",
                        team_id=f"equipe-{asset.family.team}",
                    )
                )
    history.sort(key=lambda item: (item.finished_at, item.operation_id))
    return tuple(history)


def _build_inventory(
    rng: random.Random,
    item_count: int,
    as_of: datetime,
) -> tuple[InventoryPosition, ...]:
    positions: list[InventoryPosition] = []
    for index in range(1, item_count + 1):
        item_id = f"item-{index:05d}"
        draw = rng.random()
        if draw < 0.08:
            # Sem saldo e sem entrada prevista: é o que barra uma ordem.
            positions.append(
                InventoryPosition(
                    item_id=item_id,
                    on_hand_quantity=0.0,
                    reserved_quantity=0.0,
                    lead_time_days=rng.choice([30, 45, 60, 90]),
                )
            )
            continue
        if draw < 0.14:
            # Sem saldo agora, mas com compra a caminho.
            positions.append(
                InventoryPosition(
                    item_id=item_id,
                    on_hand_quantity=0.0,
                    reserved_quantity=0.0,
                    lead_time_days=rng.choice([7, 15, 21]),
                    expected_inbound_at=as_of + timedelta(days=rng.randint(1, 20)),
                )
            )
            continue
        on_hand = float(rng.randint(1, 40))
        positions.append(
            InventoryPosition(
                item_id=item_id,
                on_hand_quantity=on_hand,
                reserved_quantity=(
                    float(rng.randint(0, int(on_hand))) if rng.random() < 0.2 else 0.0
                ),
                lead_time_days=rng.choice([7, 15, 30, 45]),
            )
        )
    return tuple(positions)


def _priority(rng: random.Random) -> int | None:
    draw = rng.random()
    if draw < 0.07:
        return 1
    if draw < 0.28:
        return 2
    if draw < 0.80:
        return 3
    if draw < 0.96:
        return 4
    return None


def _due_at(rng: random.Random, as_of: datetime, created_at: datetime) -> datetime | None:
    draw = rng.random()
    if draw < 0.08:
        return None
    if draw < 0.24:
        # Vencida: entra no topo do ranking pelo componente de SLA.
        return as_of - timedelta(days=rng.randint(1, 40))
    if draw < 0.62:
        return as_of + timedelta(days=rng.randint(1, 45))
    return max(created_at, as_of) + timedelta(days=rng.randint(46, 400))


def _build_operations(
    rng: random.Random,
    assets: Sequence[_Asset],
    inventory: Sequence[InventoryPosition],
    operation_count: int,
    as_of: datetime,
    week_start: datetime,
) -> tuple[WorkOrderOperation, ...]:
    item_ids = [position.item_id for position in inventory]
    empty_item_ids = [
        position.item_id
        for position in inventory
        if position.on_hand_quantity <= 0 and position.expected_inbound_at is None
    ]
    operations: list[WorkOrderOperation] = []
    for index in range(1, operation_count + 1):
        asset = rng.choice(assets)
        activity = rng.choice(asset.family.activities)
        label, factor = _ACTIVITIES[activity]
        base = asset.family.base_minutes * factor
        created_at = as_of - timedelta(
            days=rng.randint(1, 240), minutes=rng.randrange(0, 24 * 60, 5)
        )

        materials: tuple[MaterialRequirement, ...] = ()
        draw = rng.random()
        if draw < 0.06:
            # Pede peça que não tem saldo nem entrada: sai como sem material.
            materials = (
                MaterialRequirement(
                    item_id=rng.choice(empty_item_ids),
                    quantity=float(rng.randint(1, 3)),
                ),
            )
        elif draw < 0.38:
            quantity = float(rng.randint(1, 4))
            materials = tuple(
                MaterialRequirement(
                    item_id=rng.choice(item_ids),
                    quantity=quantity,
                    reserved_quantity=quantity if rng.random() < 0.15 else 0.0,
                )
                for _ in range(1 if rng.random() < 0.8 else 2)
            )

        blocked = rng.random() < 0.05
        windows: tuple[TimeWindow, ...] = ()
        if rng.random() < 0.05:
            # Ordem que só pode acontecer num turno específico da semana.
            day = week_start + timedelta(days=rng.randint(0, 4))
            windows = (TimeWindow(start=_local(day, 6), end=_local(day, 11)),)

        operations.append(
            WorkOrderOperation(
                work_order_id=f"wo-{index:05d}",
                operation_id=f"op-{index:05d}",
                title=f"{label} — {asset.family.label}",
                status="open",
                planning_status="unplanned" if rng.random() < 0.75 else "without_planning",
                created_at=created_at,
                due_at=_due_at(rng, as_of, created_at),
                priority_level=_priority(rng),
                criticality=(
                    None
                    if rng.random() < 0.12
                    else max(0, min(100, asset.family.criticality + rng.randint(-8, 8)))
                ),
                asset_id=asset.asset_id,
                location_id=asset.location_id,
                activity_type_id=f"atividade-{activity}",
                planned_team_id=f"equipe-{asset.family.team}",
                planned_duration_minutes=(
                    _sample_duration(rng, base) if rng.random() < 0.7 else None
                ),
                required_worker_count=1 if rng.random() < 0.88 else 2,
                required_materials=materials,
                operational_windows=windows,
                blocked=blocked,
                block_reason=rng.choice(_BLOCK_REASONS) if blocked else None,
            )
        )
    return tuple(operations)


def build_demo_snapshot(
    *,
    seed: int = DEFAULT_SEED,
    as_of: datetime | None = None,
    operation_count: int = DEFAULT_OPERATION_COUNT,
    inventory_items: int = DEFAULT_INVENTORY_ITEMS,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> PlanningSnapshot:
    """Monta o snapshot fictício completo.

    A mesma semente devolve o mesmo snapshot, então o arquivo publicado é
    reprodutível a partir do repositório: quem duvidar do dado pode regerá-lo.
    """

    if operation_count <= 0:
        raise ValueError("operation_count must be positive")
    if inventory_items <= 0:
        raise ValueError("inventory_items must be positive")

    moment = as_of or datetime(2026, 8, 17, 12, tzinfo=PLANT_TIMEZONE)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("as_of must include a timezone")
    moment = moment.astimezone(PLANT_TIMEZONE)
    week_start = _monday_of_week(moment)

    rng = random.Random(seed)
    assets = _build_assets()
    workers = _build_workers(rng)
    history = _build_history(rng, assets, workers, moment)
    inventory = _build_inventory(rng, inventory_items, moment)
    operations = _build_operations(
        rng, assets, inventory, operation_count, moment, week_start
    )

    return PlanningSnapshot(
        snapshot_id=f"demo:{tenant_id}:{moment.date().isoformat()}:{seed}",
        tenant_id=tenant_id,
        as_of=moment,
        operations=operations,
        history=history,
        inventory=inventory,
        workers=tuple(
            WorkerProfile(
                worker_id=worker.worker_id,
                team_ids=(f"equipe-{worker.team}",),
                qualification_ids=(),
                active=True,
            )
            for worker in workers
        ),
        availability=_availability(workers, week_start),
        existing_assignments=(),
        metadata={
            "source": "sintetico",
            "generator": "application.demo.synthetic",
            "seed": seed,
            "week_start": week_start.isoformat(),
            "historical_reconstruction": False,
            "rejected_records": 0,
            "notice": (
                "Dado fictício gerado por semente. Nenhuma informação de cliente "
                "real foi usada para produzir este arquivo."
            ),
        },
    )


def demo_period(snapshot: PlanningSnapshot) -> TimeWindow:
    """A semana que o snapshot foi montado para cobrir."""

    raw = snapshot.metadata.get("week_start")
    if not isinstance(raw, str):
        raise ValueError("snapshot metadata does not declare week_start")
    start = datetime.fromisoformat(raw)
    return TimeWindow(start=start, end=start + timedelta(days=7))


__all__ = [
    "DEFAULT_INVENTORY_ITEMS",
    "DEFAULT_OPERATION_COUNT",
    "DEFAULT_SEED",
    "DEFAULT_TENANT_ID",
    "PLANT_TIMEZONE",
    "build_demo_snapshot",
    "demo_period",
]

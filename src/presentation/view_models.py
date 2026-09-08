"""Transforma contratos do piloto em linhas simples para a interface."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from presentation.privacy import display_worker_id

_QUALITY_LABELS = {
    "assets_with_criticality": "Ativos com criticidade",
    "operations_with_activity_type": "Operações com tipo de atividade",
    "operations_with_due_at": "Operações com SLA",
    "operations_with_materials": "Operações com material relacionado",
    "operations_with_planned_duration": "Operações com duração planejada",
    "operations_with_priority": "Operações com prioridade",
    "operations_with_sla": "Operações com SLA",
    "rejected_records": "Registros rejeitados pelo contrato",
    "workers_with_availability": "Pessoas com disponibilidade",
}

_UNSCHEDULED_ACTIONS = {
    "blocked": "Revisar e liberar o bloqueio operacional.",
    "duration": "Informar duração ou validar o fallback histórico.",
    "material": "Revisar saldo, reserva e necessidade de compra.",
    "no_capacity": "Reavaliar período, carga ou capacidade da equipe.",
    "no_executant": "Revisar equipe, habilidade e disponibilidade.",
    "outside_period": "Mover para um período compatível.",
    "outside_window": "Confirmar uma janela operacional válida.",
}


def to_plain(value: Any) -> Any:
    """Converte Pydantic/dataclass/enums sem importar dependências de UI."""

    if hasattr(value, "model_dump"):
        return to_plain(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return to_plain(asdict(value))
    if isinstance(value, Enum):
        return to_plain(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_plain(item) for item in value]
    return value


def _mapping(value: Any) -> dict[str, Any]:
    plain = to_plain(value)
    return plain if isinstance(plain, dict) else {}


def _find_collection(value: Any, names: set[str]) -> list[dict[str, Any]]:
    plain = to_plain(value)
    if isinstance(plain, list):
        return [item for item in plain if isinstance(item, dict)]
    if not isinstance(plain, dict):
        return []
    for name in names:
        candidate = plain.get(name)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    for candidate in plain.values():
        if isinstance(candidate, dict):
            found = _find_collection(candidate, names)
            if found:
                return found
    return []


def _nested(value: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, Mapping) else {}


def _component(priority: Mapping[str, Any], name: str) -> dict[str, Any]:
    components = priority.get("components", [])
    if not isinstance(components, list):
        return {}
    return next(
        (
            component
            for component in components
            if isinstance(component, dict) and component.get("name") == name
        ),
        {},
    )


def _reason_codes(value: Mapping[str, Any]) -> tuple[str, ...]:
    reasons = value.get("reason_codes", ())
    if not isinstance(reasons, (list, tuple)):
        return ()
    return tuple(str(reason) for reason in reasons)


def _readiness(material_status: str, blocking: bool) -> str:
    """Prontidão tem três estados; desconhecido nunca vira pronto.

    Uma OS sem material cadastrado no Planta Modelo costuma indicar diagnóstico
    pendente ou item sem saldo, então afirmar prontidão seria inventar
    evidência que não existe.
    """

    if blocking:
        return "Bloqueada"
    if material_status == "unknown":
        return "Sem informação"
    return "Pronta"


def _informed(value: Any, absent_label: str) -> Any:
    """Um campo nulo é ausência declarada, nunca um valor baixo implícito.

    ``dict.get`` com default não resolve: o contrato canônico serializa o campo
    opcional como ``null`` explícito, então a chave existe e o default é ignorado.
    """

    return absent_label if value is None or value == "" else value


def _format_sla(priority: Mapping[str, Any]) -> str:
    codes = _reason_codes(priority)
    sla = _component(priority, "sla")
    raw = sla.get("raw_value")
    if "SLA_MISSING" in codes:
        return "Não informado"
    if "SLA_OVERDUE" in codes:
        return f"Vencida há {abs(float(raw or 0)):.1f} dia(s)"
    if "SLA_DUE_NOW" in codes:
        return "Vence hoje"
    if raw is None:
        return "Não informado"
    return f"{float(raw):.1f} dia(s) restante(s)"


def snapshot_rows(snapshots: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        item = _mapping(snapshot)
        metadata_value = item.get("metadata")
        metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
        quality_value = item.get("quality")
        quality: dict[str, Any] = quality_value if isinstance(quality_value, dict) else {}

        sources = (quality, item, metadata)

        def _count(*keys: str, lookup: tuple[dict[str, Any], ...] = sources) -> Any:
            for source in lookup:
                for key in keys:
                    value = source.get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        return value
            return "Não informado"

        rows.append(
            {
                "snapshot_id": item.get("snapshot_id", item.get("id", "")),
                "tenant": item.get("tenant_id", item.get("tenant", "")),
                "data_corte": item.get("as_of", item.get("created_at", "")),
                "operações": _count("operation_count", "operations_total"),
                "pessoas": _count("worker_count", "workers_total"),
                "materiais": _count("inventory_item_count", "inventory_count", "inventory_total"),
            }
        )
    return rows


def quality_rows(snapshot: Any) -> list[dict[str, Any]]:
    """Exibe indicadores persistidos; não recalcula cobertura na UI."""

    item = _mapping(snapshot)
    metadata_value = item.get("metadata")
    metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
    quality: Any = item.get("quality")
    if not isinstance(quality, dict):
        quality = metadata.get("quality", metadata.get("coverage", {}))
    if not isinstance(quality, dict):
        quality = {}

    rows: list[dict[str, Any]] = []
    indicators = quality.get("indicators")
    if isinstance(indicators, list):
        for indicator in indicators:
            if not isinstance(indicator, dict):
                continue
            key = str(indicator.get("key", "unknown"))
            rows.append(
                {
                    "indicador": _QUALITY_LABELS.get(
                        key,
                        key.replace("_", " ").capitalize(),
                    ),
                    "valor": indicator.get("coverage_percent", "—"),
                    "afetados": indicator.get("missing", "—"),
                    "presentes": indicator.get("present", "—"),
                    "total": indicator.get("total", "—"),
                    "campo": key,
                }
            )
        return rows

    for key, value in sorted(quality.items()):
        if isinstance(value, dict):
            displayed = value.get("percentage", value.get("value", value.get("count", "—")))
            affected = value.get("affected", value.get("missing", "—"))
        else:
            displayed = value
            affected = "—"
        rows.append(
            {
                "indicador": _QUALITY_LABELS.get(key, key.replace("_", " ").capitalize()),
                "valor": displayed,
                "afetados": affected,
                "campo": key,
            }
        )
    return rows


def backlog_items(payload: Any) -> list[dict[str, Any]]:
    return _find_collection(payload, {"backlog", "enriched", "items", "operations"})


def backlog_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items = backlog_items(payload)
    ordered = sorted(
        items,
        key=lambda item: (
            -float(_nested(item, "priority").get("score", 0)),
            str(_nested(item, "operation").get("operation_id", item.get("operation_id", ""))),
        ),
    )
    for position, item in enumerate(ordered, start=1):
        operation = _nested(item, "operation") or item
        priority = _nested(item, "priority")
        materials = _nested(item, "materials")
        duration = _nested(item, "duration")
        executants = item.get("executants", [])
        eligible_count = sum(
            1
            for candidate in executants
            if isinstance(candidate, dict) and candidate.get("eligible") is True
        ) if isinstance(executants, list) else 0
        age = _component(priority, "age").get("raw_value")
        material_status = str(materials.get("status", "unknown"))
        scheduled = item.get("scheduled")
        rows.append(
            {
                "posição": position,
                "os": operation.get("work_order_id", ""),
                "operação": operation.get("operation_id", item.get("operation_id", "")),
                "título": operation.get("title", ""),
                "prioridade": _informed(operation.get("priority_level"), "Não informada"),
                "idade_dias": round(float(age), 1) if age is not None else None,
                "sla": _format_sla(priority),
                "vencida": "SLA_OVERDUE" in _reason_codes(priority),
                "due_at": operation.get("due_at"),
                "criticidade": _informed(operation.get("criticality"), "Não informada"),
                "score": priority.get("score", 0),
                "modelo": priority.get("model", ""),
                "material": material_status,
                "prontidão": _readiness(material_status, bool(materials.get("blocking"))),
                "programabilidade": (
                    "Programável"
                    if duration.get("minutes") is not None and eligible_count > 0
                    else "Com pendência"
                ),
                "programada": scheduled,
                "localização": _informed(operation.get("location_id"), "Não informada"),
                "ativo": _informed(operation.get("asset_id"), "Não informado"),
            }
        )
    return rows


def filter_backlog(
    rows: Iterable[Mapping[str, Any]],
    *,
    overdue_only: bool = False,
    due_before: datetime | None = None,
    priorities: set[str] | None = None,
    locations: set[str] | None = None,
    assets: set[str] | None = None,
    material_statuses: set[str] | None = None,
    scheduled: bool | None = None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        if overdue_only and not row.get("vencida"):
            continue
        if due_before is not None and row.get("due_at"):
            try:
                due_at = datetime.fromisoformat(str(row["due_at"]).replace("Z", "+00:00"))
            except ValueError:
                due_at = None
            if due_at is None or due_at > due_before:
                continue
        if priorities and str(row.get("prioridade")) not in priorities:
            continue
        if locations and str(row.get("localização")) not in locations:
            continue
        if assets and str(row.get("ativo")) not in assets:
            continue
        if material_statuses and str(row.get("material")) not in material_statuses:
            continue
        if scheduled is not None and row.get("programada") is not scheduled:
            continue
        result.append(row)
    return result


def operation_detail(payload: Any, operation_id: str) -> dict[str, Any]:
    for item in backlog_items(payload):
        operation = _nested(item, "operation") or item
        if str(operation.get("operation_id", item.get("operation_id", ""))) == operation_id:
            return item
    return {}


def duration_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in backlog_items(payload):
        operation = _nested(item, "operation") or item
        duration = _nested(item, "duration")
        planned = operation.get("planned_duration_minutes")
        adopted = duration.get("minutes")
        divergence = None
        if isinstance(planned, (int, float)) and isinstance(adopted, (int, float)) and planned:
            divergence = round((float(adopted) - float(planned)) / float(planned) * 100, 1)
        rows.append(
            {
                "operação": operation.get("operation_id", ""),
                "planejada_min": planned,
                "adotada_min": adopted,
                "p50_min": duration.get("p50_minutes"),
                "p80_min": duration.get("p80_minutes"),
                "fonte": duration.get("source"),
                "amostra": duration.get("sample_size"),
                "confiança": duration.get("confidence"),
                "divergência_%": divergence,
                "motivos": ", ".join(_reason_codes(duration)),
            }
        )
    return rows


def material_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in backlog_items(payload):
        operation = _nested(item, "operation") or item
        materials = _nested(item, "materials")
        lines = materials.get("lines", [])
        if not isinstance(lines, list) or not lines:
            lines = [{}]
        for line in lines:
            if not isinstance(line, dict):
                continue
            rows.append(
                {
                    "operação": operation.get("operation_id", ""),
                    "item": line.get("item_id", "—"),
                    "requerido": line.get("required_quantity", "—"),
                    "disponível_líquido": line.get("available_quantity", "—"),
                    "faltante": line.get("missing_quantity", "—"),
                    "lead_time_dias": line.get("lead_time_days", "—"),
                    "estado": materials.get("status", "unknown"),
                    "bloqueador": bool(materials.get("blocking")),
                    "motivo": line.get("reason_code", ", ".join(_reason_codes(materials))),
                }
            )
    return rows


def capacity_rows(payload: Any, *, reveal_workers: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for capacity in _find_collection(payload, {"capacities", "capacity", "workers_capacity"}):
        worker_id = str(capacity.get("worker_id", ""))
        slots = capacity.get("slots", [])
        rows.append(
            {
                "executante": display_worker_id(worker_id, reveal=reveal_workers),
                "HH_bruto": round(float(capacity.get("gross_minutes", 0)) / 60, 2),
                "HH_comprometido": round(float(capacity.get("committed_minutes", 0)) / 60, 2),
                "HH_líquido": round(float(capacity.get("net_minutes", 0)) / 60, 2),
                "slots": len(slots) if isinstance(slots, list) else 0,
            }
        )
    return rows


def executant_rows(payload: Any, *, reveal_workers: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in backlog_items(payload):
        operation = _nested(item, "operation") or item
        executants = item.get("executants", [])
        if not isinstance(executants, list):
            continue
        for position, candidate in enumerate(executants, start=1):
            if not isinstance(candidate, dict):
                continue
            worker_id = str(candidate.get("worker_id", ""))
            rows.append(
                {
                    "operação": operation.get("operation_id", ""),
                    "posição": position,
                    "executante": display_worker_id(worker_id, reveal=reveal_workers),
                    "score": candidate.get("score", 0),
                    "HH_disponível": round(
                        float(candidate.get("available_minutes", 0)) / 60,
                        2,
                    ),
                    "elegível": bool(candidate.get("eligible")),
                    "evidências": ", ".join(_reason_codes(candidate)),
                }
            )
    return rows


def schedule_rows(
    payload: Any,
    backlog_payload: Any | None = None,
    *,
    reveal_workers: bool = False,
) -> list[dict[str, Any]]:
    assignments = _find_collection(payload, {"assignments"})
    operation_context = {
        str((_nested(item, "operation") or item).get("operation_id", "")): (
            _nested(item, "operation") or item
        )
        for item in backlog_items(backlog_payload)
    } if backlog_payload is not None else {}
    rows: list[dict[str, Any]] = []
    for assignment in assignments:
        window_value = assignment.get("window")
        window: dict[str, Any] = window_value if isinstance(window_value, dict) else {}
        worker_ids = assignment.get("worker_ids", [])
        if not isinstance(worker_ids, list):
            worker_ids = [worker_ids]
        aliases = [
            display_worker_id(str(worker_id), reveal=reveal_workers)
            for worker_id in worker_ids
        ]
        start = window.get("start")
        end = window.get("end")
        duration_minutes = None
        if start and end:
            try:
                parsed_start = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                parsed_end = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
                duration_minutes = int((parsed_end - parsed_start).total_seconds() // 60)
            except ValueError:
                duration_minutes = None
        context = operation_context.get(str(assignment.get("operation_id", "")), {})
        rows.append(
            {
                "os": assignment.get("work_order_id", ""),
                "operação": assignment.get("operation_id", ""),
                "executantes": ", ".join(aliases),
                "início": start,
                "fim": end,
                "duração_min": duration_minutes,
                "prioridade_score": assignment.get("priority_score", 0),
                "equipe": context.get("planned_team_id", "Não informada"),
                "localização": context.get("location_id", "Não informada"),
                "ativo": context.get("asset_id", "Não informado"),
                "regras_aplicadas": ", ".join(_reason_codes(assignment)),
            }
        )
    return rows


def unscheduled_rows(
    schedule_payload: Any, backlog_payload: Any | None = None
) -> list[dict[str, Any]]:
    scores = {
        str(row["operação"]): row.get("score", 0)
        for row in backlog_rows(backlog_payload)
    } if backlog_payload is not None else {}
    rows: list[dict[str, Any]] = []
    for item in _find_collection(schedule_payload, {"unscheduled"}):
        reason = str(item.get("reason", "unknown"))
        operation_id = str(item.get("operation_id", ""))
        details = item.get("details", [])
        rows.append(
            {
                "os": item.get("work_order_id", ""),
                "operação": operation_id,
                "prioridade_score": scores.get(operation_id, 0),
                "motivo": reason,
                "detalhes": ", ".join(str(detail) for detail in details),
                "próxima_ação": _UNSCHEDULED_ACTIONS.get(
                    reason,
                    "Revisar os dados e as restrições da operação.",
                ),
            }
        )
    return sorted(rows, key=lambda row: (-float(row["prioridade_score"]), row["operação"]))


def coverage_view(payload: Any) -> dict[str, Any]:
    """Traduz a cobertura de capacidade para a leitura do planejador."""

    data = _mapping(payload)
    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        coverage = data if "capacity_limited_operations" in data else {}

    def _number(key: str) -> float:
        value = coverage.get(key, 0)
        return float(value) if isinstance(value, (int, float)) else 0.0

    unscheduled = int(_number("unscheduled_operations"))
    capacity_limited = int(_number("capacity_limited_operations"))
    percent = round(_number("coverage_percent"), 2)
    return {
        "cobertura_percent": percent,
        "demanda_hh": round(_number("demand_minutes") / 60, 2),
        "disponível_hh": round(_number("available_minutes") / 60, 2),
        "programadas": int(_number("scheduled_operations")),
        "não_programadas": unscheduled,
        "limite_de_capacidade": capacity_limited,
        "outros_motivos": max(0, unscheduled - capacity_limited),
        "leitura": (
            f"A capacidade disponível cobre {percent:.1f}% da demanda do backlog. "
            f"{capacity_limited} das {unscheduled} não programadas são limite de "
            "capacidade, não falha de recomendação."
        ),
    }


def verification_view(payload: Any) -> dict[str, Any]:
    data = _mapping(payload)
    if "verification" in data and isinstance(data["verification"], dict):
        data = data["verification"]
    violations = data.get("violations", [])
    rows = (
        [item for item in violations if isinstance(item, dict)]
        if isinstance(violations, list)
        else []
    )
    return {
        "valid": bool(data.get("valid", False)),
        "input_hash": data.get("input_hash", ""),
        "violations": rows,
        "error_count": sum(1 for row in rows if str(row.get("severity")) == "error"),
    }


def selected_operation_id(selection: Any, rows: list[dict[str, Any]]) -> str | None:
    """Traduz a seleção de linha do Streamlit no identificador da operação."""

    payload = _mapping(selection).get("selection")
    if not isinstance(payload, Mapping):
        return None
    indexes = payload.get("rows")
    if not isinstance(indexes, (list, tuple)) or not indexes:
        return None
    index = indexes[0]
    if not isinstance(index, int) or not 0 <= index < len(rows):
        return None
    return str(rows[index].get("operação", "")) or None


def run_id(value: Any) -> str | None:
    item = _mapping(value)
    identifier = item.get("run_id", item.get("id"))
    return str(identifier) if identifier is not None else None


def run_rows(runs: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        item = _mapping(run)
        proposal_value = item.get("proposal")
        proposal: dict[str, Any] = (
            proposal_value if isinstance(proposal_value, dict) else {}
        )
        solution_value = proposal.get("solution")
        solution: dict[str, Any] = (
            solution_value if isinstance(solution_value, dict) else {}
        )
        rows.append(
            {
                "run_id": item.get("run_id", item.get("id", "")),
                "snapshot_id": item.get("snapshot_id", proposal.get("snapshot_id", "")),
                "status": item.get("status", proposal.get("status", "")),
                "criado_em": item.get("created_at", ""),
                "alocações": item.get("assignments", len(solution.get("assignments", []))),
                "não_programadas": item.get(
                    "unscheduled",
                    len(solution.get("unscheduled", [])),
                ),
                "decisão": item.get("decision", "Pendente"),
            }
        )
    return rows


READY_STATUSES = frozenset({"completed", "complete", "ready", "succeeded", "success"})

_PLANNING_STAGE_COUNT = 6


def execution_progress(run: Any) -> int:
    """Percentual derivado das etapas realmente concluídas, não de um chute."""

    status = run_status_view(run)["status"]
    if status in READY_STATUSES:
        return 100
    completed = len(trace_rows(run))
    return min(100, round(completed / _PLANNING_STAGE_COUNT * 100))


def run_status_view(run: Any) -> dict[str, Any]:
    item = _mapping(run)
    status = item.get("status", "unknown")
    if isinstance(status, dict):
        status = status.get("value", "unknown")
    return {
        "run_id": item.get("run_id", item.get("id", "")),
        "status": str(status).casefold(),
        "error": item.get("error", item.get("error_code")),
        "created_at": item.get("created_at"),
        "completed_at": item.get("completed_at"),
    }


def trace_rows(run: Any) -> list[dict[str, Any]]:
    events = _find_collection(run, {"trace", "trace_events"})
    rows: list[dict[str, Any]] = []
    for event in events:
        if not event.get("stage"):
            continue
        raw_counts = event.get("counts")
        counts: dict[str, Any] = raw_counts if isinstance(raw_counts, dict) else {}
        rows.append(
            {
                "sequência": event.get("sequence", len(rows) + 1),
                "etapa": event.get("stage", ""),
                "tempo_ms": event.get("elapsed_ms", 0),
                "registros": ", ".join(
                    f"{key}: {value}" for key, value in sorted(counts.items())
                ),
            }
        )
    return sorted(rows, key=lambda row: int(row["sequência"]))


__all__ = [
    "READY_STATUSES",
    "backlog_items",
    "backlog_rows",
    "capacity_rows",
    "duration_rows",
    "execution_progress",
    "executant_rows",
    "filter_backlog",
    "material_rows",
    "operation_detail",
    "quality_rows",
    "run_id",
    "run_rows",
    "run_status_view",
    "schedule_rows",
    "selected_operation_id",
    "snapshot_rows",
    "to_plain",
    "trace_rows",
    "unscheduled_rows",
    "verification_view",
]

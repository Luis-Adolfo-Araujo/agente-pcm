from __future__ import annotations

from application.pilot.models import RunStatus
from presentation.view_models import execution_progress

STAGES = [
    "snapshot_validated",
    "skills_parallel",
    "executant_candidates",
    "optimization",
    "verification",
    "proposal_ready",
]


def _run(status: str, stage_count: int) -> dict[str, object]:
    return {
        "status": status,
        "trace_events": [
            {"sequence": index + 1, "stage": STAGES[index], "elapsed_ms": 1.0, "counts": {}}
            for index in range(stage_count)
        ],
    }


def test_a_queued_run_has_not_started() -> None:
    assert execution_progress(_run("queued", 0)) == 0


def test_progress_follows_the_stages_actually_completed() -> None:
    assert execution_progress(_run("running", 3)) == 50


def test_a_completed_run_is_full_regardless_of_trace() -> None:
    assert execution_progress(_run("completed", 6)) == 100


def test_a_failed_run_keeps_the_progress_it_reached() -> None:
    assert execution_progress(_run("failed", 2)) == 33


def test_a_wrapped_status_shape_is_recognized_as_ready() -> None:
    """execution_progress must normalize status exactly like run_status_view.

    The service can hand back status as ``{"value": "completed"}`` instead of
    a bare string; run_status_view already unwraps that shape. If
    execution_progress reads the raw field instead, the progress bar stalls
    on the trace count while the rest of the screen already reports ready.
    """

    run = {"status": {"value": "completed"}, "trace_events": []}

    assert execution_progress(run) == 100


def test_an_interrupted_run_never_reports_full_progress() -> None:
    """Interrupted is a real terminal RunStatus, but it is not ready.

    pages.py and view_models.py each kept their own copy of the
    ready-status vocabulary. Two copies drift silently: add a terminal
    status to one and the analytical screens unlock while the progress bar
    stalls below 100 (or the reverse). Pin both the single shared source
    and the concrete status that would expose a drift: RunStatus.INTERRUPTED
    must never be read as ready, so execution_progress must stay partial.
    """

    from presentation import pages
    from presentation.view_models import READY_STATUSES

    assert pages._READY_STATUSES is READY_STATUSES
    assert RunStatus.INTERRUPTED.value not in READY_STATUSES
    assert execution_progress(_run(RunStatus.INTERRUPTED.value, 3)) != 100

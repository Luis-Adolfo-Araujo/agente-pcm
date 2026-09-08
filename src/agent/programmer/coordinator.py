"""Fachada do Agente Programador sobre o workflow determinístico."""

from collections.abc import Callable
from pathlib import Path

from agent.skills.core.registry import SkillRegistry
from application.workflows.generate_schedule import generate_schedule
from domain.planning.config import PlanningConfig
from domain.planning.entities import (
    PlanningRequest,
    PlanningRunResult,
    PlanningSnapshot,
    PlanningStageTrace,
)


class ProgrammerAgent:
    def __init__(
        self,
        config: PlanningConfig | None = None,
        skill_root: Path | None = None,
    ) -> None:
        self._config = config or PlanningConfig()
        root = skill_root or Path(__file__).resolve().parents[1] / "skills" / "pcm"
        self._skills = SkillRegistry.from_directory(root)

    @property
    def skill_names(self) -> tuple[str, ...]:
        return self._skills.enabled_names

    async def propose(
        self,
        request: PlanningRequest,
        snapshot: PlanningSnapshot,
        *,
        stage_listener: Callable[[PlanningStageTrace], None] | None = None,
    ) -> PlanningRunResult:
        versions = {
            skill.name: skill.version
            for skill in self._skills.load_all()
        }
        return await generate_schedule(
            request,
            snapshot,
            self._config,
            skill_versions=versions,
            stage_listener=stage_listener,
        )

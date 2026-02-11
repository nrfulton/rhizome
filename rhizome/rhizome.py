from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mellea.core.backend import Backend

from rhizome.agent import Agent, AgentHandle
from rhizome.beat import BeatRecord, run_beat
from rhizome.compost import CompostPile
from rhizome.environment import Environment
from rhizome.human import HumanInput


@dataclass
class RhizomeConfig:
    root: Path
    concurrency: int = 4


class Rhizome:
    """Shared blackboard for multi-agent orchestration.

    The Rhizome is not a scheduler — it holds shared state. The beat cycle
    and gardener handle activation mechanically based on precondition satisfaction.
    """

    def __init__(self, config: RhizomeConfig, backend: Backend) -> None:
        self.config = config
        self.backend = backend
        self.environment = Environment(config.root)
        self.compost = CompostPile()
        self.handles: list[AgentHandle] = []
        self.humanity: list[HumanInput] = []
        self.beat_count: int = 0
        self._human_input_cursor: int = 0  # tracks processed human inputs

    async def initialize(self) -> None:
        """Load persisted state if it exists."""
        self.compost = await CompostPile.load(self.environment.compost_path)

    def register(self, agent: Agent) -> AgentHandle:
        """Register an agent and return its handle."""
        handle = AgentHandle(agent=agent)
        self.handles.append(handle)
        return handle

    def human_input(self, content: str) -> HumanInput:
        """Record human input. This will trigger interrupt on next beat."""
        inp = HumanInput(content=content)
        self.humanity.append(inp)
        return inp

    def has_unprocessed_human_input(self) -> bool:
        """Check if there's human input since the last beat."""
        return self._human_input_cursor < len(self.humanity)

    def mark_human_input_processed(self) -> None:
        """Mark all current human input as processed."""
        self._human_input_cursor = len(self.humanity)

    async def beat(self) -> BeatRecord:
        """Run one beat of the rhizome."""
        return await run_beat(self, concurrency=self.config.concurrency)

    async def run(self, max_beats: int | None = None) -> list[BeatRecord]:
        """Run beats until quiescent or max_beats reached."""
        records: list[BeatRecord] = []
        beats_run = 0

        while max_beats is None or beats_run < max_beats:
            record = await self.beat()
            records.append(record)
            beats_run += 1

            # Quiescent: nothing happened and no pending human input
            if (
                not record.activated
                and not record.completed
                and not record.killed
                and not self.has_unprocessed_human_input()
            ):
                break

        return records

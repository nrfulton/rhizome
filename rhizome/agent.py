from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from mellea.core.base import Context
from mellea.core.backend import Backend
from mellea.core.requirement import Requirement

if TYPE_CHECKING:
    from rhizome.rhizome import Rhizome


@runtime_checkable
class MelleaProgram(Protocol):
    async def __call__(
        self, rhizome: Rhizome, backend: Backend, ctx: Context
    ) -> None: ...


class AgentStatus(enum.Enum):
    DORMANT = "dormant"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


@dataclass(frozen=True)
class Agent:
    name: str
    needs: tuple[Requirement, ...]
    fun: Any  # MelleaProgram — Any to avoid runtime protocol check overhead
    abilities: tuple[Requirement, ...]
    background: bool = False


@dataclass
class AgentHandle:
    agent: Agent
    status: AgentStatus = AgentStatus.DORMANT
    handle_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    error: BaseException | None = field(default=None, repr=False)
    _task: Any = field(default=None, repr=False)  # asyncio.Task when RUNNING

    @property
    def name(self) -> str:
        return self.agent.name

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.KILLED,
        )

    def transition(self, new_status: AgentStatus) -> None:
        _VALID_TRANSITIONS = {
            AgentStatus.DORMANT: (AgentStatus.PENDING, AgentStatus.KILLED),
            AgentStatus.PENDING: (AgentStatus.RUNNING, AgentStatus.KILLED),
            AgentStatus.RUNNING: (
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
                AgentStatus.KILLED,
            ),
        }
        allowed = _VALID_TRANSITIONS.get(self.status, ())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value} "
                f"for agent '{self.name}'"
            )
        self.status = new_status

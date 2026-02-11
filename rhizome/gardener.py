from __future__ import annotations

from typing import TYPE_CHECKING

from mellea.core.backend import Backend

from rhizome.agent import AgentHandle, AgentStatus
from rhizome.context_views import GardenerView

if TYPE_CHECKING:
    from rhizome.rhizome import Rhizome


class Gardener:
    """Mechanical need-checker. Evaluates dormant agents' preconditions.

    The Gardener does not decide whether to activate an agent — it only
    checks whether the agent's needs are satisfied. The decision was made
    when the agent was registered with those needs.
    """

    def __init__(self, backend: Backend) -> None:
        self.backend = backend

    async def evaluate(self, rhizome: Rhizome) -> list[AgentHandle]:
        """Check all dormant agents. Returns handles that were activated (DORMANT → PENDING)."""
        gardener_view = GardenerView.from_rhizome(rhizome)
        activated: list[AgentHandle] = []

        dormant = [
            h for h in rhizome.handles if h.status == AgentStatus.DORMANT
        ]

        for handle in dormant:
            if not handle.agent.needs:
                # No preconditions — activate immediately
                handle.transition(AgentStatus.PENDING)
                activated.append(handle)
                continue

            all_satisfied = True
            for req in handle.agent.needs:
                result = await req.validate(self.backend, gardener_view)
                if not result:
                    all_satisfied = False
                    break

            if all_satisfied:
                handle.transition(AgentStatus.PENDING)
                activated.append(handle)

        return activated

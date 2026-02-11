from __future__ import annotations

from typing import TYPE_CHECKING

from mellea.core.base import CBlock, Component, Context, ModelOutputThunk

if TYPE_CHECKING:
    from rhizome.rhizome import Rhizome


class GlobalRhizomeView(Context):
    """High-level summary view: active agents, recent compost, environment status.

    Used as context for agent programs that need situational awareness.
    """

    def __init__(self) -> None:
        super().__init__()

    def add(self, c: Component | CBlock) -> GlobalRhizomeView:
        new = GlobalRhizomeView.from_previous(self, c)
        return new

    def view_for_generation(self) -> list[Component | CBlock] | None:
        return self.as_list()

    @classmethod
    def from_rhizome(cls, rhizome: Rhizome) -> GlobalRhizomeView:
        ctx = cls()

        # Active agents summary
        from rhizome.agent import AgentStatus

        agents = rhizome.handles
        active = [h for h in agents if not h.is_terminal]
        dormant = [h for h in agents if h.status == AgentStatus.DORMANT]
        running = [h for h in agents if h.status == AgentStatus.RUNNING]

        agent_summary = (
            f"Agents: {len(agents)} total, {len(active)} active, "
            f"{len(dormant)} dormant, {len(running)} running"
        )
        ctx = ctx.add(CBlock(agent_summary))

        # Recent compost entries
        entries = rhizome.compost.active_entries()
        if entries:
            recent = entries[-10:]  # last 10
            compost_lines = ["Recent compost entries:"]
            for e in recent:
                compost_lines.append(f"  [{e.author}] {e.key}: {e.content[:200]}")
            ctx = ctx.add(CBlock("\n".join(compost_lines)))

        # Humanity list
        if rhizome.humanity:
            recent_human = rhizome.humanity[-5:]
            human_lines = ["Recent human inputs:"]
            for h in recent_human:
                human_lines.append(f"  [{h.timestamp.isoformat()}] {h.content}")
            ctx = ctx.add(CBlock("\n".join(human_lines)))

        # Environment status
        try:
            files = rhizome.environment.list_files()
            ctx = ctx.add(CBlock(f"Environment: {len(files)} tracked files"))
        except Exception:
            ctx = ctx.add(CBlock("Environment: not initialized"))

        return ctx


class RhizomeAgentAnthology(Context):
    """History of agent activity: completed runs, summaries, event order.

    Used for agents that need to understand the project's history.
    """

    def __init__(self) -> None:
        super().__init__()

    def add(self, c: Component | CBlock) -> RhizomeAgentAnthology:
        new = RhizomeAgentAnthology.from_previous(self, c)
        return new

    def view_for_generation(self) -> list[Component | CBlock] | None:
        return self.as_list()

    @classmethod
    def from_rhizome(cls, rhizome: Rhizome) -> RhizomeAgentAnthology:
        ctx = cls()

        # All compost entries in chronological order — this IS the history
        entries = rhizome.compost.all_entries()
        for entry in entries:
            stale_marker = " [superseded]" if entry._stale else ""
            ctx = ctx.add(
                CBlock(
                    f"[{entry.timestamp.isoformat()}] {entry.author} → {entry.key}{stale_marker}\n"
                    f"{entry.content}"
                )
            )

        return ctx


class GardenerView(Context):
    """Synthetic context for Requirement.validate() during gardener evaluation.

    Contains current rhizome state as CBlocks, with a synthetic ModelOutputThunk
    as the last element so LLM-as-judge requirements can evaluate against it.
    """

    def __init__(self) -> None:
        super().__init__()

    def add(self, c: Component | CBlock) -> GardenerView:
        new = GardenerView.from_previous(self, c)
        return new

    def view_for_generation(self) -> list[Component | CBlock] | None:
        return self.as_list()

    @classmethod
    def from_rhizome(cls, rhizome: Rhizome) -> GardenerView:
        ctx = cls()

        # Build a text representation of current state
        state_parts = []

        # Compost state
        entries = rhizome.compost.active_entries()
        if entries:
            state_parts.append("=== Compost Pile ===")
            for e in entries:
                state_parts.append(f"[{e.author}] {e.key}: {e.content}")

        # Human inputs
        if rhizome.humanity:
            state_parts.append("\n=== Human Inputs ===")
            for h in rhizome.humanity:
                state_parts.append(f"[{h.timestamp.isoformat()}] {h.content}")

        # Environment files
        try:
            files = rhizome.environment.list_files()
            if files:
                state_parts.append(f"\n=== Environment ({len(files)} files) ===")
                for f in files[:50]:  # cap at 50 files
                    state_parts.append(f"  {f}")
        except Exception:
            pass

        # Agent states
        from rhizome.agent import AgentStatus

        state_parts.append("\n=== Agents ===")
        for h in rhizome.handles:
            state_parts.append(f"  {h.name} [{h.status.value}]")

        state_text = "\n".join(state_parts) if state_parts else "(empty rhizome)"

        # Add the state as a CBlock
        ctx = ctx.add(CBlock(state_text))

        # Add a synthetic ModelOutputThunk so LLM-as-judge requirements
        # can use ctx.last_output() to get the "output" to judge
        thunk = ModelOutputThunk(state_text)
        thunk._computed = True
        ctx = ctx.add(thunk)

        return ctx

import asyncio
import tempfile
from pathlib import Path

from collections.abc import Sequence

from mellea.core.backend import Backend
from mellea.core.base import CBlock, Component, Context, ModelOutputThunk
from mellea.core.requirement import Requirement, ValidationResult

from rhizome import Agent, Rhizome, RhizomeConfig
from rhizome.compost import CompostEntry


class StubBackend(Backend):
    """Minimal backend for examples that only use validation_fn requirements."""

    async def generate_from_context(self, action, ctx, **kwargs):
        mot = ModelOutputThunk(value="stub")
        return mot, ctx.add(action).add(mot)

    async def generate_from_raw(self, actions, ctx, **kwargs):
        return [ModelOutputThunk(value="stub") for _ in actions]


# -- Example agents --


async def bootstrap_agent(rhizome: Rhizome, backend: Backend, ctx: Context) -> None:
    """First agent to run. Sets up initial state in the compost pile."""
    await rhizome.compost.add(
        CompostEntry(
            key="bootstrap:status",
            content="Rhizome initialized. Awaiting human input.",
            author="bootstrap",
        )
    )
    print("[bootstrap] Rhizome initialized.")


async def echo_agent(rhizome: Rhizome, backend: Backend, ctx: Context) -> None:
    """Echoes the latest human input into the compost pile."""
    if rhizome.humanity:
        last = rhizome.humanity[-1]
        await rhizome.compost.add(
            CompostEntry(
                key="echo:last_input",
                content=f"Human said: {last.content}",
                author="echo",
                supersedes="echo:last_input",
            )
        )
        print(f"[echo] {last.content}")


def has_human_input(ctx: Context) -> ValidationResult:
    last = ctx.last_output()
    if last and last.value and "Human Inputs" in last.value:
        return ValidationResult(True)
    return ValidationResult(False, reason="No human input yet")


async def main() -> None:
    # Use a temp directory so we don't pollute the working tree
    with tempfile.TemporaryDirectory() as tmpdir:
        config = RhizomeConfig(root=Path(tmpdir))

        # Use a dummy backend — no LLM calls needed for this example
        # since all requirements use validation_fn
        backend = StubBackend()

        r = Rhizome(config, backend)
        await r.initialize()

        # Register agents
        r.register(
            Agent(
                name="bootstrap",
                needs=(),
                fun=bootstrap_agent,
                abilities=(),
            )
        )

        r.register(
            Agent(
                name="echo",
                needs=(Requirement(validation_fn=has_human_input),),
                fun=echo_agent,
                abilities=(),
            )
        )

        # Beat 1: bootstrap runs (empty needs), echo stays dormant
        print("--- Beat 1 ---")
        record = await r.beat()
        print(f"  Activated: {record.activated}, Completed: {record.completed}")

        # Human input arrives
        r.human_input("Hello, rhizome!")

        # Beat 2: echo activates (human input exists)
        print("--- Beat 2 ---")
        record = await r.beat()
        print(f"  Activated: {record.activated}, Completed: {record.completed}")

        # Beat 3: quiescent — nothing new to do
        print("--- Beat 3 ---")
        record = await r.beat()
        print(f"  Activated: {record.activated}, Completed: {record.completed}")

        print("\nCompost pile:")
        for entry in r.compost.active_entries():
            print(f"  [{entry.author}] {entry.key}: {entry.content[:80]}")


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rhizome.agent import AgentHandle, AgentStatus
from rhizome.compost import CompostEntry
from rhizome.context_views import GlobalRhizomeView
from rhizome.gardener import Gardener

if TYPE_CHECKING:
    from rhizome.rhizome import Rhizome


@dataclass
class BeatRecord:
    beat_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    killed: list[str] = field(default_factory=list)
    activated: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    postcondition_warnings: list[str] = field(default_factory=list)
    commit_sha: str | None = None


async def run_beat(
    rhizome: Rhizome,
    *,
    concurrency: int = 4,
) -> BeatRecord:
    """Execute one beat of the rhizome. Implements the 6-phase algorithm."""
    record = BeatRecord(beat_number=rhizome.beat_count)
    gardener = Gardener(rhizome.backend)
    has_new_human_input = rhizome.has_unprocessed_human_input()

    # ── Phase 1: Interrupt ──
    if has_new_human_input:
        for handle in rhizome.handles:
            if handle.status in (AgentStatus.RUNNING, AgentStatus.PENDING):
                if not handle.agent.background:
                    handle.transition(AgentStatus.KILLED)
                    record.killed.append(handle.name)
                    await rhizome.compost.add(
                        CompostEntry(
                            key=f"beat:{record.beat_number}:killed:{handle.handle_id}",
                            content=f"Agent '{handle.name}' killed by human interrupt",
                            author="beat",
                        )
                    )

    rhizome.mark_human_input_processed()

    # ── Phase 2: Background agents ──
    background_handles = [
        h
        for h in rhizome.handles
        if h.agent.background and h.status == AgentStatus.DORMANT
    ]
    for handle in background_handles:
        handle.transition(AgentStatus.PENDING)

    for handle in background_handles:
        await _run_agent(rhizome, handle, record)

    # ── Phase 3: Gardener evaluation ──
    activated = await gardener.evaluate(rhizome)
    for handle in activated:
        record.activated.append(handle.name)

    # ── Phase 4: Concurrent execution ──
    pending = [h for h in rhizome.handles if h.status == AgentStatus.PENDING]
    if pending:
        sem = asyncio.Semaphore(concurrency)

        async def run_bounded(h: AgentHandle) -> None:
            async with sem:
                await _run_agent(rhizome, h, record)

        await asyncio.gather(*(run_bounded(h) for h in pending))

    # ── Phase 5: Postcondition assertion ──
    completed_handles = [
        h for h in rhizome.handles if h.status == AgentStatus.COMPLETED
    ]
    for handle in completed_handles:
        if handle.agent.abilities:
            from rhizome.context_views import GardenerView

            post_view = GardenerView.from_rhizome(rhizome)
            for req in handle.agent.abilities:
                try:
                    result = await req.validate(rhizome.backend, post_view)
                    if not result:
                        warning = (
                            f"Postcondition not met for '{handle.name}': "
                            f"{req.description or 'unnamed requirement'}"
                        )
                        record.postcondition_warnings.append(warning)
                        await rhizome.compost.add(
                            CompostEntry(
                                key=f"beat:{record.beat_number}:postcondition_warning:{handle.handle_id}",
                                content=warning,
                                author="beat",
                            )
                        )
                except Exception:
                    warning = (
                        f"Postcondition check failed for '{handle.name}': "
                        f"{traceback.format_exc()}"
                    )
                    record.postcondition_warnings.append(warning)

    # ── Phase 6: Persist ──
    summary_lines = [f"Beat {record.beat_number} summary:"]
    if record.killed:
        summary_lines.append(f"  Killed: {', '.join(record.killed)}")
    if record.activated:
        summary_lines.append(f"  Activated: {', '.join(record.activated)}")
    if record.completed:
        summary_lines.append(f"  Completed: {', '.join(record.completed)}")
    if record.failed:
        summary_lines.append(f"  Failed: {', '.join(record.failed)}")
    if record.postcondition_warnings:
        summary_lines.append(
            f"  Postcondition warnings: {len(record.postcondition_warnings)}"
        )

    await rhizome.compost.add(
        CompostEntry(
            key=f"beat:{record.beat_number}:summary",
            content="\n".join(summary_lines),
            author="beat",
        )
    )

    await rhizome.compost.save(rhizome.environment.compost_path)
    record.commit_sha = rhizome.environment.commit(
        f"beat {record.beat_number}"
    )

    rhizome.beat_count += 1
    return record


async def _run_agent(
    rhizome: Rhizome, handle: AgentHandle, record: BeatRecord
) -> None:
    """Run a single agent, handling lifecycle transitions and errors."""
    handle.transition(AgentStatus.RUNNING)
    try:
        ctx = GlobalRhizomeView.from_rhizome(rhizome)
        await handle.agent.fun(rhizome, rhizome.backend, ctx)
        handle.transition(AgentStatus.COMPLETED)
        record.completed.append(handle.name)
    except Exception as exc:
        handle.error = exc
        handle.transition(AgentStatus.FAILED)
        record.failed.append(handle.name)
        await rhizome.compost.add(
            CompostEntry(
                key=f"agent:{handle.handle_id}:error",
                content=f"Agent '{handle.name}' failed: {exc}\n{traceback.format_exc()}",
                author=handle.name,
            )
        )

"""Agent intelligence MCP tools for Taskwarrior."""

import json
from datetime import datetime, timezone

from mcp.types import ToolAnnotations

from taskwarrior_mcp.enums import ResponseFormat, TaskStatus
from taskwarrior_mcp.models.inputs import (
    BlockedInput,
    ContextInput,
    DependenciesInput,
    ReadyInput,
    SuggestInput,
    TriageInput,
)
from taskwarrior_mcp.models.intelligence import (
    BlockedTaskInfo,
    BottleneckInfo,
    ComputedInsights,
    ScoredTask,
)
from taskwarrior_mcp.models.task import TaskModel
from taskwarrior_mcp.server import mcp
from taskwarrior_mcp.utils.cli import _get_tasks_json, _run_task_command
from taskwarrior_mcp.utils.formatters import _format_task_concise, _format_tasks_concise
from taskwarrior_mcp.utils.parsers import _parse_task, _parse_tasks

# ============================================================================
# Agent Intelligence Helper Functions
# ============================================================================


def _calculate_suggestion_score(task: TaskModel, all_tasks: list[TaskModel]) -> tuple[float, list[str]]:
    """
    Calculate suggestion score for a task and return reasons.

    Returns:
        Tuple of (score, list_of_reasons)
    """
    score = 0.0
    reasons: list[str] = []

    # Base urgency from Taskwarrior
    urgency = task.urgency

    # Overdue: urgency > 12 typically indicates overdue
    if urgency > 12:
        score += 100
        reasons.append("Overdue")
    elif urgency > 8:
        score += 50
        reasons.append("Due soon")

    # High priority
    if task.priority == "H":
        score += 30
        reasons.append("High priority")
    elif task.priority == "M":
        score += 15

    # Currently active (started)
    if task.start:
        score += 15
        reasons.append("Currently active")

    # Tagged +next
    if "next" in task.tags:
        score += 25
        reasons.append("Tagged +next")

    # Quick wins (tagged quick or low urgency with no dependencies)
    if "quick" in task.tags:
        score += 10
        reasons.append("Quick win")

    # Blocks other tasks
    task_uuid = task.uuid or ""
    blocked_count = 0
    for t in all_tasks:
        if t.depends and task_uuid in t.depends:
            blocked_count += 1

    if blocked_count > 0:
        score += 20 * blocked_count
        reasons.append(f"Blocks {blocked_count} task(s)")

    # Add base urgency
    score += urgency

    return score, reasons


def _get_blocked_tasks(tasks: list[TaskModel]) -> list[TaskModel]:
    """Get tasks that have unresolved dependencies."""
    # Build a set of pending task UUIDs
    pending_uuids = {t.uuid for t in tasks if t.status == "pending" and t.uuid}

    blocked: list[TaskModel] = []
    for task in tasks:
        if task.status != "pending":
            continue
        if task.depends:
            # Check if any dependency is still pending
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            has_pending_dep = any(d in pending_uuids for d in dep_uuids)
            if has_pending_dep:
                blocked.append(task)

    return blocked


def _get_ready_tasks(tasks: list[TaskModel]) -> list[TaskModel]:
    """Get tasks that have no pending dependencies."""
    pending_uuids = {t.uuid for t in tasks if t.status == "pending" and t.uuid}

    ready: list[TaskModel] = []
    for task in tasks:
        if task.status != "pending":
            continue
        if not task.depends:
            ready.append(task)
        else:
            # Check if all dependencies are completed
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            has_pending_dep = any(d in pending_uuids for d in dep_uuids)
            if not has_pending_dep:
                ready.append(task)

    return ready


def _get_task_age_str(task: TaskModel) -> str:
    """Get human-readable age of a task."""
    if not task.entry:
        return "Unknown"

    try:
        # Taskwarrior uses ISO format: 20250130T100000Z
        entry_dt = datetime.strptime(task.entry[:15], "%Y%m%dT%H%M%S")
        entry_dt = entry_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - entry_dt

        days = delta.days
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week(s) ago"
        else:
            months = days // 30
            return f"{months} month(s) ago"
    except (ValueError, TypeError):
        return "Unknown"


def _is_task_stale(task: TaskModel, stale_days: int) -> bool:
    """Check if a task is stale (not modified recently)."""
    modified = task.modified or task.entry
    if not modified:
        return True

    try:
        mod_dt = datetime.strptime(modified[:15], "%Y%m%dT%H%M%S")
        mod_dt = mod_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - mod_dt
        return delta.days >= stale_days
    except (ValueError, TypeError):
        return False


# ============================================================================
# Agent Intelligence Tool Definitions
# ============================================================================


@mcp.tool(
    name="taskwarrior_suggest",
    annotations=ToolAnnotations(
        title="Suggest Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_suggest(params: SuggestInput) -> str:
    """
    Get AI-powered task recommendations for what to work on next.

    USE THIS WHEN:
    - User asks "what should I work on?" or "what's important?"
    - Planning a work session and need prioritized suggestions
    - Need reasoning for why tasks are important (overdue, blocks others, etc.)

    DO NOT USE WHEN:
    - You just want a simple task list → use taskwarrior_list instead
    - You specifically want blocked tasks → use taskwarrior_blocked
    - You want unblocked/ready tasks only → use taskwarrior_ready
    - You want details on a specific task → use taskwarrior_get or taskwarrior_context

    CONTEXT OPTIONS:
    - None (default): Balanced suggestions considering all factors
    - "quick_wins": Tasks that can be completed quickly (low urgency, tagged +quick)
    - "blockers": Tasks that unblock other work (completing these helps most)
    - "deadlines": Tasks with imminent or past due dates

    Args:
        params: SuggestInput with limit, context, project filter, and format

    Returns:
        Prioritized list of task suggestions with reasons (e.g., "Blocks 3 tasks", "Overdue")

    Examples:
        - Get top 5 suggestions: params with default values
        - Focus on blockers: params with context="blockers"
        - Filter to project: params with project="work"
    """
    # Get all pending tasks
    filter_expr = f"project:{params.project}" if params.project else None
    success, result = _get_tasks_json(filter_expr, TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    tasks = _parse_tasks(raw_tasks)
    if not tasks:
        return "# Suggestions\n\nNo pending tasks found. Nothing to suggest!"

    # Score each task
    scored_tasks: list[ScoredTask] = []
    for task in tasks:
        score, reasons = _calculate_suggestion_score(task, tasks)
        scored_tasks.append(ScoredTask(task=task, score=score, reasons=reasons))

    # Sort by score descending
    scored_tasks.sort(key=lambda x: x.score, reverse=True)

    # Apply context filter if specified
    if params.context == "quick_wins":
        scored_tasks = [s for s in scored_tasks if "Quick win" in s.reasons or s.task.urgency < 5]
    elif params.context == "blockers":
        scored_tasks = [s for s in scored_tasks if any("Blocks" in r for r in s.reasons)]
    elif params.context == "deadlines":
        scored_tasks = [s for s in scored_tasks if "Overdue" in s.reasons or "Due soon" in s.reasons]

    # Limit results
    scored_tasks = scored_tasks[: params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "suggestions": [s.model_dump() for s in scored_tasks],
                "total_pending": len(tasks),
            },
            indent=2,
        )

    if params.response_format == ResponseFormat.CONCISE:
        if not scored_tasks:
            return "0 suggestions"
        lines = [f"{len(scored_tasks)} suggestion(s)"]
        for s in scored_tasks:
            reason_short = s.reasons[0] if s.reasons else ""
            lines.append(f"{_format_task_concise(s.task)} [{reason_short}]")
        return "\n".join(lines)

    # Markdown format
    if not scored_tasks:
        return "# Suggestions\n\nNo tasks match your criteria."

    lines = ["# Suggested: What to Work On", ""]

    for i, s in enumerate(scored_tasks, 1):
        task = s.task
        task_id = task.id if task.id else "?"
        desc = task.description or "No description"
        reasons = s.reasons

        # Add status indicator
        indicator = ""
        if "Overdue" in reasons:
            indicator = "⚠️ OVERDUE"
        elif "Due soon" in reasons:
            indicator = "📅 DUE SOON"
        elif "Quick win" in reasons:
            indicator = "⚡ QUICK WIN"
        elif "Currently active" in reasons:
            indicator = "🔄 ACTIVE"

        lines.append(f"{i}. **[#{task_id}] {desc}** {indicator}")

        # Details line
        details = []
        if task.due:
            details.append(f"Due: {task.due[:10]}")
        if task.priority:
            details.append(f"Priority: {task.priority}")
        if task.project:
            details.append(f"Project: {task.project}")

        if details:
            lines.append(f"   {' | '.join(details)}")

        # Reason line
        if reasons:
            lines.append(f"   → Reason: {', '.join(reasons)}")

        lines.append("")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_ready",
    annotations=ToolAnnotations(
        title="Ready Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_ready(params: ReadyInput) -> str:
    """
    List tasks that can be started immediately (no pending dependencies).

    USE THIS WHEN:
    - You want to see what tasks are unblocked and actionable
    - Looking for tasks that don't require other tasks to complete first
    - Answering "what can I actually work on right now?"

    DO NOT USE WHEN:
    - You want prioritized suggestions with reasoning → use taskwarrior_suggest
    - You want to see blocked tasks → use taskwarrior_blocked
    - You want a general task list without dependency checking → use taskwarrior_list

    Args:
        params: ReadyInput with limit, project, priority, and format options

    Returns:
        List of unblocked tasks ready to start

    Examples:
        - Get ready tasks: params with default values
        - Filter by project: params with project="work"
        - High priority only: params with priority="H"
    """
    # Get all pending tasks (need all to check dependencies)
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)
    ready_tasks = _get_ready_tasks(all_tasks)

    # Apply filters
    if params.project:
        ready_tasks = [t for t in ready_tasks if t.project == params.project]

    if params.priority:
        ready_tasks = [t for t in ready_tasks if t.priority == params.priority]

    if not params.include_active:
        ready_tasks = [t for t in ready_tasks if not t.start]

    # Sort by urgency descending
    ready_tasks.sort(key=lambda t: t.urgency, reverse=True)

    # Limit
    ready_tasks = ready_tasks[: params.limit]

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "tasks": [t.model_dump() for t in ready_tasks],
                "count": len(ready_tasks),
                "total_pending": len(all_tasks),
            },
            indent=2,
        )

    if params.response_format == ResponseFormat.CONCISE:
        return _format_tasks_concise(ready_tasks, "ready")

    # Markdown format
    if not ready_tasks:
        return "# Ready to Work\n\nNo unblocked tasks found."

    lines = [f"# Ready to Work ({len(ready_tasks)} tasks)", ""]
    lines.append("| ID | Task | Priority | Due | Project |")
    lines.append("|----|------|----------|-----|---------|")

    for task in ready_tasks:
        task_id = task.id if task.id else "?"
        desc = task.description[:40] if task.description else ""
        priority = task.priority or "-"
        due = task.due[:10] if task.due else "-"
        project = task.project or "-"

        # Mark overdue
        if task.urgency > 12:
            due = f"**{due}** ⚠️"

        lines.append(f"| {task_id} | {desc} | {priority} | {due} | {project} |")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_blocked",
    annotations=ToolAnnotations(
        title="Blocked Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_blocked(params: BlockedInput) -> str:
    """
    List tasks that are waiting on other tasks to complete.

    USE THIS WHEN:
    - You want to see tasks that can't be started yet
    - Understanding what's holding up progress
    - Identifying dependency chains

    DO NOT USE WHEN:
    - You want tasks you CAN work on → use taskwarrior_ready instead
    - You want full dependency graph analysis → use taskwarrior_dependencies
    - You want prioritized suggestions → use taskwarrior_suggest

    Args:
        params: BlockedInput with limit, show_blockers option, and format

    Returns:
        List of blocked tasks with their blockers

    Examples:
        - Get blocked tasks: params with default values
        - Without blocker details: params with show_blockers=False
    """
    # Get all pending tasks
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)
    blocked_tasks = _get_blocked_tasks(all_tasks)

    # Limit
    blocked_tasks = blocked_tasks[: params.limit]

    # Build UUID to task mapping for showing blockers
    uuid_to_task = {t.uuid: t for t in all_tasks if t.uuid}

    if params.response_format == ResponseFormat.JSON:
        blocked_info: list[BlockedTaskInfo] = []
        for task in blocked_tasks:
            info = BlockedTaskInfo(task=task, blockers=[])
            if params.show_blockers and task.depends:
                dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
                for dep_uuid in dep_uuids:
                    blocker = uuid_to_task.get(dep_uuid)
                    if blocker and blocker.status == "pending":
                        info.blockers.append(blocker)
            blocked_info.append(info)

        return json.dumps(
            {
                "blocked": [b.model_dump() for b in blocked_info],
                "count": len(blocked_tasks),
                "total_pending": len(all_tasks),
            },
            indent=2,
        )

    if params.response_format == ResponseFormat.CONCISE:
        return _format_tasks_concise(blocked_tasks, "blocked")

    # Markdown format
    if not blocked_tasks:
        return "# Blocked Tasks\n\nNo blocked tasks found. All tasks are ready to work on!"

    lines = [f"# Blocked Tasks ({len(blocked_tasks)} waiting)", ""]

    for i, task in enumerate(blocked_tasks, 1):
        task_id = task.id if task.id else "?"
        desc = task.description or "No description"

        lines.append(f"{i}. **[#{task_id}] {desc}**")

        if params.show_blockers and task.depends:
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            blockers_list = []
            for dep_uuid in dep_uuids:
                blocker = uuid_to_task.get(dep_uuid)
                if blocker and blocker.status == "pending":
                    blocker_id = blocker.id if blocker.id else "?"
                    blocker_desc = blocker.description[:30] if blocker.description else ""
                    blockers_list.append(f"#{blocker_id} ({blocker_desc})")

            if blockers_list:
                lines.append(f"   Blocked by: {', '.join(blockers_list)}")

        lines.append("")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_dependencies",
    annotations=ToolAnnotations(
        title="Task Dependencies",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_dependencies(params: DependenciesInput) -> str:
    """
    Analyze dependency relationships and identify bottlenecks.

    USE THIS WHEN:
    - Understanding the dependency graph (what blocks what)
    - Finding critical bottleneck tasks that block many others
    - Analyzing a specific task's dependencies in both directions

    DO NOT USE WHEN:
    - You just want a list of blocked tasks → use taskwarrior_blocked
    - You want tasks ready to start → use taskwarrior_ready
    - You want task details without dependency analysis → use taskwarrior_get

    MODES:
    - Overview (task_id=None): Shows bottlenecks and blocked/ready counts
    - Specific task: Shows what the task blocks and what blocks it

    DIRECTION OPTIONS (for specific task):
    - "both": Show tasks it blocks AND tasks blocking it
    - "blocks": Only show tasks waiting on this one
    - "blocked_by": Only show tasks this one depends on

    Args:
        params: DependenciesInput with optional task_id, direction, depth

    Returns:
        Dependency graph analysis (overview or specific task)

    Examples:
        - Get overview: params with task_id=None
        - Specific task: params with task_id="5"
        - Only what task blocks: params with task_id="5", direction="blocks"
    """
    # Get all tasks (pending and completed for full picture)
    success, result = _get_tasks_json(status=TaskStatus.ALL)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)
    pending_tasks = [t for t in all_tasks if t.status == "pending"]

    # Build UUID to task mapping
    uuid_to_task = {t.uuid: t for t in all_tasks if t.uuid}

    # Build "blocks" relationships (what each task blocks)
    blocks_map: dict[str, list[TaskModel]] = {}  # uuid -> list of tasks it blocks
    for task in pending_tasks:
        if task.depends:
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            for dep_uuid in dep_uuids:
                if dep_uuid not in blocks_map:
                    blocks_map[dep_uuid] = []
                blocks_map[dep_uuid].append(task)

    if params.task_id:
        # Specific task analysis
        success, output = _run_task_command([params.task_id, "export"])
        if not success:
            return output

        try:
            task_list = json.loads(output) if output else []
            if not task_list:
                return (
                    f"Error: Task '{params.task_id}' not found.\n"
                    f"Tip: Use taskwarrior_list to find valid task IDs, "
                    f"or check if the task was completed/deleted."
                )
            task = _parse_task(task_list[0])
        except json.JSONDecodeError:
            return (
                f"Error: Could not parse task '{params.task_id}'.\n"
                f"Tip: This may indicate a Taskwarrior configuration issue."
            )

        task_uuid = task.uuid or ""
        task_id = task.id if task.id else params.task_id
        desc = task.description or "No description"

        # What this task blocks
        blocks = blocks_map.get(task_uuid, [])

        # What blocks this task
        blocked_by: list[TaskModel] = []
        if task.depends:
            dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
            for dep_uuid in dep_uuids:
                blocker = uuid_to_task.get(dep_uuid)
                if blocker:
                    blocked_by.append(blocker)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "task": task.model_dump(),
                    "blocks": [b.model_dump() for b in blocks] if params.direction in ["both", "blocks"] else [],
                    "blocked_by": [b.model_dump() for b in blocked_by]
                    if params.direction in ["both", "blocked_by"]
                    else [],
                    "ready": len([b for b in blocked_by if b.status == "pending"]) == 0,
                },
                indent=2,
            )

        # Markdown format
        lines = [f"# Dependencies for #{task_id}: {desc}", ""]

        if params.direction in ["both", "blocks"]:
            lines.append(f"### ⬇️ Blocks ({len(blocks)} task(s) waiting)")
            if blocks:
                for b in blocks:
                    status = "✓ COMPLETED" if b.status == "completed" else ""
                    b_id = b.id if b.id else "?"
                    lines.append(f"├── #{b_id}: {b.description} {status}")
            else:
                lines.append("(None)")
            lines.append("")

        if params.direction in ["both", "blocked_by"]:
            lines.append(f"### ⬆️ Blocked By ({len(blocked_by)} task(s) required)")
            if blocked_by:
                for b in blocked_by:
                    status = "✓ COMPLETED" if b.status == "completed" else ""
                    b_id = b.id if b.id else "?"
                    lines.append(f"└── #{b_id}: {b.description} {status}")
            else:
                lines.append("(None)")
            lines.append("")

        # Assessment
        pending_blockers = [b for b in blocked_by if b.status == "pending"]
        ready = len(pending_blockers) == 0
        impact = "HIGH" if len(blocks) >= 2 else "MEDIUM" if len(blocks) == 1 else "LOW"

        lines.append("### Assessment")
        status_text = "READY TO START" if ready else f"BLOCKED by {len(pending_blockers)} task(s)"
        lines.append(f"- Status: {status_text}")
        lines.append(f"- Impact: {impact} (unblocks {len(blocks)} task(s))")

        return "\n".join(lines)

    else:
        # Overview mode
        # Find bottlenecks (tasks that block the most others)
        bottlenecks: list[BottleneckInfo] = []
        for uuid, blocked_list in blocks_map.items():
            bottleneck_task = uuid_to_task.get(uuid)
            if bottleneck_task is not None and bottleneck_task.status == "pending":
                bottlenecks.append(BottleneckInfo(task=bottleneck_task, blocks_count=len(blocked_list)))

        bottlenecks.sort(key=lambda x: x.blocks_count, reverse=True)

        blocked_tasks = _get_blocked_tasks(pending_tasks)
        ready_tasks = _get_ready_tasks(pending_tasks)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "bottlenecks": [b.model_dump() for b in bottlenecks[:10]],
                    "blocked": [t.id for t in blocked_tasks[:10]],
                    "ready": [t.id for t in ready_tasks[:10]],
                    "stats": {
                        "total_pending": len(pending_tasks),
                        "blocked_count": len(blocked_tasks),
                        "ready_count": len(ready_tasks),
                    },
                },
                indent=2,
            )

        # Markdown format
        lines = ["# Dependency Overview", ""]

        lines.append("### Critical Bottlenecks")
        if bottlenecks[:5]:
            for bottleneck in bottlenecks[:5]:
                t_id = bottleneck.task.id if bottleneck.task.id else "?"
                lines.append(f"- #{t_id} blocks {bottleneck.blocks_count} downstream task(s)")
        else:
            lines.append("(No bottlenecks)")
        lines.append("")

        lines.append(f"### Blocked Tasks ({len(blocked_tasks)} cannot start)")
        if blocked_tasks[:5]:
            for t in blocked_tasks[:5]:
                t_id = t.id if t.id else "?"
                desc = t.description[:40] if t.description else ""
                lines.append(f"- #{t_id}: {desc}")
        else:
            lines.append("(None)")
        lines.append("")

        lines.append(f"### Ready to Work ({len(ready_tasks)} unblocked)")
        if ready_tasks[:5]:
            lines.append(", ".join([f"#{t.id}" for t in ready_tasks[:5] if t.id]))
        else:
            lines.append("(None)")

        return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_triage",
    annotations=ToolAnnotations(
        title="Triage Tasks",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_triage(params: TriageInput) -> str:
    """
    Find tasks that need attention: stale, unorganized, or forgotten.

    USE THIS WHEN:
    - Doing a weekly review or task cleanup
    - Finding tasks that fell through the cracks
    - Identifying poorly organized tasks (no project, no tags, no due date)

    DO NOT USE WHEN:
    - You want suggestions on what to work on → use taskwarrior_suggest
    - You want to see all tasks → use taskwarrior_list
    - You want blocked/ready status → use taskwarrior_blocked or taskwarrior_ready

    CATEGORIES IDENTIFIED:
    - Stale: Not modified in X days (default 14)
    - No project: Tasks without a project assignment
    - Untagged: Tasks with no tags
    - No due date: Tasks without a deadline

    Args:
        params: TriageInput with stale_days, filter options, and format

    Returns:
        Categorized list of tasks needing attention

    Examples:
        - Default triage: params with default values
        - Only stale tasks: params with include_untagged=False, include_no_project=False
        - More aggressive: params with stale_days=7
    """
    success, result = _get_tasks_json(status=TaskStatus.PENDING)

    if not success:
        return str(result)

    raw_tasks = result if isinstance(result, list) else []
    all_tasks = _parse_tasks(raw_tasks)

    # Categorize tasks
    stale: list[TaskModel] = []
    no_project: list[TaskModel] = []
    untagged: list[TaskModel] = []
    no_due: list[TaskModel] = []

    for task in all_tasks:
        if params.include_untagged and not task.tags:
            untagged.append(task)

        if params.include_no_project and not task.project:
            no_project.append(task)

        if params.include_no_due and not task.due:
            no_due.append(task)

        if _is_task_stale(task, params.stale_days):
            stale.append(task)

    # Limit each category
    stale = stale[: params.limit]
    no_project = no_project[: params.limit]
    untagged = untagged[: params.limit]
    no_due = no_due[: params.limit]

    total_items = len(stale) + len(no_project) + len(untagged) + len(no_due)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "stale": [t.model_dump() for t in stale],
                "no_project": [t.model_dump() for t in no_project],
                "untagged": [t.model_dump() for t in untagged],
                "no_due": [t.model_dump() for t in no_due],
                "total_items": total_items,
                "total_pending": len(all_tasks),
            },
            indent=2,
        )

    # Markdown format
    if total_items == 0:
        return "# Task Triage\n\nLooking good! No items need attention."

    lines = [f"# Task Triage - {total_items} items need attention", ""]

    if stale:
        stale_header = f"### 🕸️ Stale Tasks (>{params.stale_days} days) - {len(stale)} items"
        lines.append(stale_header)
        lines.append("| ID | Task | Age | Last Modified |")
        lines.append("|----|------|-----|---------------|")
        for task in stale:
            task_id = task.id if task.id else "?"
            desc = task.description[:30] if task.description else ""
            age = _get_task_age_str(task)
            modified = (task.modified or task.entry or "")[:10]
            lines.append(f"| {task_id} | {desc} | {age} | {modified} |")
        lines.append("")

    if no_project:
        lines.append(f"### 📁 No Project Assigned - {len(no_project)} items")
        lines.append("| ID | Task | Created |")
        lines.append("|----|------|---------|")
        for task in no_project:
            task_id = task.id if task.id else "?"
            desc = task.description[:40] if task.description else ""
            created = task.entry[:10] if task.entry else ""
            lines.append(f"| {task_id} | {desc} | {created} |")
        lines.append("")

    if untagged:
        lines.append(f"### 🏷️ Untagged Tasks - {len(untagged)} items")
        lines.append("| ID | Task | Project |")
        lines.append("|----|------|---------|")
        for task in untagged:
            task_id = task.id if task.id else "?"
            desc = task.description[:40] if task.description else ""
            project = task.project or "-"
            lines.append(f"| {task_id} | {desc} | {project} |")
        lines.append("")

    if no_due:
        lines.append(f"### 📅 No Due Date - {len(no_due)} items")
        lines.append("| ID | Task | Priority | Project |")
        lines.append("|----|------|----------|---------|")
        for task in no_due:
            task_id = task.id if task.id else "?"
            desc = task.description[:30] if task.description else ""
            priority = task.priority or "-"
            project = task.project or "-"
            lines.append(f"| {task_id} | {desc} | {priority} | {project} |")
        lines.append("")

    lines.append("### Triage Actions")
    lines.append("- Consider: archive, delete, set due date, assign project, or add to +next")

    return "\n".join(lines)


@mcp.tool(
    name="taskwarrior_context",
    annotations=ToolAnnotations(
        title="Task Context",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def taskwarrior_context(params: ContextInput) -> str:
    """
    Get comprehensive context for a task with insights and related tasks.

    USE THIS WHEN:
    - You need deep understanding of a task before working on it
    - You want computed insights (age, dependency status, related tasks)
    - Preparing to discuss or plan around a specific task

    DO NOT USE WHEN:
    - You just need basic task details → use taskwarrior_get instead
    - You want multiple tasks → use taskwarrior_bulk_get or taskwarrior_list
    - You want dependency graph analysis → use taskwarrior_dependencies

    INCLUDES:
    - All task attributes and annotations
    - Computed age and last activity
    - Dependency status (ready, blocked, blocks others)
    - Related tasks from the same project

    Args:
        params: ContextInput with task_id and options for related/activity info

    Returns:
        Rich task details with computed insights

    Examples:
        - Get full context: params with task_id="5"
        - Task only: params with task_id="5", include_related=False
    """
    # Get the specific task
    success, output = _run_task_command([params.task_id, "export"])

    if not success:
        return output

    try:
        task_list = json.loads(output) if output else []
        if not task_list:
            return (
                f"Error: Task '{params.task_id}' not found.\n"
                f"Tip: Use taskwarrior_list to find valid task IDs, "
                f"or check if the task was completed/deleted."
            )
        task = _parse_task(task_list[0])
    except json.JSONDecodeError as e:
        return f"Error: Failed to parse task data - {str(e)}\nTip: This may indicate a Taskwarrior configuration issue."

    # Get all tasks for dependency and related analysis
    success, all_result = _get_tasks_json(status=TaskStatus.ALL)
    raw_all_tasks = all_result if success and isinstance(all_result, list) else []
    all_tasks = _parse_tasks(raw_all_tasks)
    pending_tasks = [t for t in all_tasks if t.status == "pending"]

    # Compute additional fields
    task_uuid = task.uuid or ""
    age = _get_task_age_str(task)

    # Dependency status
    blocking_count = 0
    blocked_by_count = 0

    if task.depends:
        dep_uuids = [d.strip() for d in task.depends.split(",") if d.strip()]
        uuid_to_task = {t.uuid: t for t in all_tasks if t.uuid}
        blocked_by_count = sum(1 for d in dep_uuids if uuid_to_task.get(d) and uuid_to_task[d].status == "pending")

    for t in pending_tasks:
        if t.depends and task_uuid in t.depends:
            blocking_count += 1

    if blocked_by_count > 0:
        dep_status = f"Blocked by {blocked_by_count} task(s)"
    elif blocking_count > 0:
        dep_status = f"Blocks {blocking_count} task(s)"
    else:
        dep_status = "Ready"

    # Related tasks (same project)
    related: list[TaskModel] = []
    if params.include_related and task.project:
        related = [t for t in pending_tasks if t.project == task.project and t.uuid != task_uuid][:5]

    # Last modified
    last_activity = "Unknown"
    if task.modified:
        try:
            mod_dt = datetime.strptime(task.modified[:15], "%Y%m%dT%H%M%S")
            now = datetime.now(timezone.utc)
            mod_dt = mod_dt.replace(tzinfo=timezone.utc)
            delta = now - mod_dt
            if delta.days == 0:
                hours = delta.seconds // 3600
                last_activity = f"{hours} hour(s) ago" if hours > 0 else "Recently"
            elif delta.days == 1:
                last_activity = "Yesterday"
            else:
                last_activity = f"{delta.days} days ago"
        except (ValueError, TypeError):
            pass

    computed = ComputedInsights(
        age=age,
        last_activity=last_activity,
        dependency_status=dep_status,
        related_pending=len(related),
        annotations_count=len(task.annotations),
    )

    if params.response_format == ResponseFormat.JSON:
        return json.dumps(
            {
                "task": task.model_dump(),
                "computed": computed.model_dump(),
                "related_tasks": [t.model_dump() for t in related] if params.include_related else [],
            },
            indent=2,
        )

    # Markdown format
    task_id = task.id if task.id else params.task_id
    desc = task.description or "No description"
    status = task.status

    lines = [f"# Task Context: #{task_id}", ""]
    lines.append(f"**{desc}**")
    lines.append("")

    # Basic info
    lines.append("### Details")
    if task.project:
        lines.append(f"- **Project**: {task.project}")
    if task.priority:
        priority_map = {"H": "High", "M": "Medium", "L": "Low"}
        lines.append(f"- **Priority**: {priority_map.get(task.priority, task.priority)}")
    if task.due:
        lines.append(f"- **Due**: {task.due}")
    if task.tags:
        lines.append(f"- **Tags**: {', '.join(task.tags)}")
    lines.append(f"- **Status**: {status}")
    lines.append(f"- **Urgency**: {task.urgency:.2f}")
    lines.append("")

    # Computed insights
    lines.append("### Insights")
    lines.append(f"- **Age**: Created {age}")
    lines.append(f"- **Last Activity**: {last_activity}")
    lines.append(f"- **Dependencies**: {dep_status}")
    if computed.annotations_count > 0:
        lines.append(f"- **Notes**: {computed.annotations_count} annotation(s)")
    lines.append("")

    # Annotations
    if task.annotations:
        lines.append("### Notes")
        for ann in task.annotations:
            entry = ann.entry[:10] if ann.entry else ""
            lines.append(f"- [{entry}] {ann.description}")
        lines.append("")

    # Related tasks
    if params.include_related and related:
        lines.append(f"### Related Tasks ({len(related)} in same project)")
        for r in related:
            r_id = r.id if r.id else "?"
            r_desc = r.description[:40] if r.description else ""
            lines.append(f"- #{r_id}: {r_desc}")

    return "\n".join(lines)

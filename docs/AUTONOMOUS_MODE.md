# AUTONOMOUS_MODE — Long autonomous Claude Code runs

## Purpose
Enable long autonomous runs while preventing scope creep.

## How to enable
In Claude Code, send:

Autonomous Execution Mode is now enabled.
Work only on tasks listed in docs/WORK_QUEUE.md Phase 1.5.
Follow AGENTS.md rules strictly.
Stop only if you need Phase 2 approval.

## Mandatory stop conditions
The agent MUST stop and ask if:
- Work would start Phase 2
- Work expands scope beyond WORK_QUEUE
- A new dependency is required without justification

## Required cadence per task
1. Update or add tests first (when relevant)
2. Run pytest
3. Implement
4. Run pytest
5. Commit
6. Update docs/PROJECT_STATUS.md if state changed

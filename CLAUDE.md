# Subagent Model Selection

When spawning subagents via the Agent tool, always set the `model` parameter based on task complexity:

- **haiku** — Simple lookups, file searches, quick grep/glob tasks, status checks, reading docs
- **sonnet** — Code exploration, moderate research, code review, test running, plan creation
- **opus** — Only for tasks requiring deep reasoning, complex multi-file refactors, or architectural decisions

Default to **sonnet** when unsure. Never use opus for subagents unless the task genuinely requires it.

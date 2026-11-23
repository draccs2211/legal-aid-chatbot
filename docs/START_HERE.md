# Start here (for the owner)

Open the project in VS Code, open Claude Code, set permission mode to plan / ask (NOT Auto), then paste this:

"Read CLAUDE.md, docs/PROJECT_STATE.md, docs/ROADMAP.md, docs/GOALS.md and docs/HISTORY.md. Do not edit anything yet.
Run git status -sb, git log --oneline -5 and the full test suite. Tell me in simple English: the real state of the repo,
whether it matches the docs, and what the next roadmap item is with a plan. Then wait for my approval."

To continue on any later day, paste:
"Continue the roadmap. Read docs/PROJECT_STATE.md 'Next session' first, then propose the plan for the next unchecked item."

Detailed prompts per task: docs/claude-code-prompts.md.
Rules you must hold the line on: say NO if Claude Code wants to read .env, push to main, merge, or force-push.

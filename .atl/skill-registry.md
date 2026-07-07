# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When creating a GitHub issue, reporting a bug, or requesting a feature. | issue-creation | C:\Users\ariza\.claude\skills\issue-creation\SKILL.md |
| When creating a pull request, opening a PR, or preparing changes for review. | branch-pr | C:\Users\ariza\.claude\skills\branch-pr\SKILL.md |
| When user asks to create a new skill, add agent instructions, or document patterns for AI. | skill-creator | C:\Users\ariza\.claude\skills\skill-creator\SKILL.md |
| When writing Go tests, using teatest, or adding test coverage. | go-testing | C:\Users\ariza\.claude\skills\go-testing\SKILL.md |
| When user says "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen". | judgment-day | C:\Users\ariza\.claude\skills\judgment-day\SKILL.md |
| Use when user asks about libraries/frameworks/API references/code examples. | context7-mcp | C:\Users\ariza\.cursor\skills\context7-mcp\SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### issue-creation
- Blank issues are disabled: always use bug_report or feature_request template.
- New issues must carry `status:needs-review`; do not bypass the workflow.
- PR creation is blocked until maintainers add `status:approved`.
- Questions belong in Discussions, not Issues.
- Check duplicates with `gh issue list --search` before creating a new issue.
- Complete all required template fields (repro, expected/actual behavior, affected area).

### branch-pr
- Every PR must link an approved issue (`Closes/Fixes/Resolves #N`).
- Use branch naming `type/description` with allowed types and lowercase slug.
- PR must include exactly one `type:*` label matching the PR type.
- Keep conventional commits with valid type/scope format.
- Run required quality checks before PR (shellcheck when scripts changed).
- Do not include `Co-Authored-By` trailers.

### skill-creator
- Create skills only for reusable, non-trivial patterns.
- Follow structure `skills/{name}/SKILL.md` (+ optional assets/references).
- Frontmatter must include `name`, `description` with Trigger, license, metadata.
- Prioritize critical actionable patterns over long explanations.
- Use local references for docs; avoid web URLs in `references/`.
- Register the new skill in project conventions/index after creation.

### go-testing
- Prefer table-driven tests for function behavior matrices.
- Test Bubbletea state transitions via `Model.Update()` directly.
- Use `teatest` for interactive full-flow TUI scenarios.
- Use golden files for stable view/output assertions.
- Cover success + error paths explicitly in each test case.
- Use `t.TempDir()` and mocks/interfaces for side-effect boundaries.

### judgment-day
- Run two blind judges in parallel; never sequential review.
- Resolve and inject project standards (skill registry compact rules) before judging.
- Synthesize findings as confirmed/suspect/contradiction with severity.
- Fix only confirmed CRITICAL and real WARNING issues.
- Re-judge after fixes; escalate to user after two iterations if issues persist.
- Classify `WARNING (theoretical)` as INFO (report, don’t block).

### context7-mcp
- For library/framework/API questions, fetch docs via Context7 (do not rely on memory only).
- First resolve library ID with `resolve-library-id`, then query docs with `query-docs`.
- Pick the best match by exact name, quality score, and official source.
- If user specifies a version, prefer versioned library IDs.
- Use user’s full query for better relevance in documentation retrieval.
- Incorporate retrieved examples and version context in final answers.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| — | — | No project-level convention files detected (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, `copilot-instructions.md`). |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.

# `docs/ai-portability.md` — using this template with AI tools other than Claude Code

This template is built around Claude Code conventions (`CLAUDE.md`, `@`-imports, `.claude/agents/`, `.claude/skills/`, `.claude/settings.json`). The *content* — operating rules, domain conventions, FORRT documentation, draft scaffolds — is plain markdown that any AI assistant can read. This doc explains how to map the Claude-specific structure onto other AI tools.

## What's portable

These artefacts work with **any AI** that reads markdown:

- `CLAUDE.md` and `AGENTS.md` — same content, two filenames so different tools find it.
- `DOMAIN.md` — domain conventions.
- `USER_PREFERENCES.md` — per-user style.
- `docs/*.md` — reference material (FORRT form fields, chain decision tree, FAIR4RS checklist, etc.).
- `nanopubs/drafts/*.md` — field-by-field draft scaffolds.

You can use the template with any AI by ensuring the AI loads `CLAUDE.md` (or `AGENTS.md`) at session start and references the `docs/` material on demand.

## What's Claude-specific

These artefacts use Claude Code-specific mechanisms but contain *content* that ports:

| Artefact | Claude-specific mechanism | Content that ports |
|---|---|---|
| `CLAUDE.md` `@`-imports of `DOMAIN.md` / `USER_PREFERENCES.md` | Claude Code automatically resolves `@path` imports at session start | Tell other AIs to read those files manually at session start |
| `.claude/agents/paper-analyst.md` etc. | Claude Code's sub-agent dispatch (`Agent({subagent_type: "paper-analyst"})`) | The prompt body inside the file is reusable as a system prompt or rule for any AI |
| `.claude/skills/init-template/SKILL.md` etc. | Claude Code's `/skill-name` slash commands | Same — copy the SKILL.md body as a system prompt for the equivalent task |
| `.claude/settings.json` permissions | Claude Code's sandbox model | Other AIs have their own permission systems; not directly transferable |

## Per-tool setup

### Cursor

Cursor reads `.cursor/rules/*.mdc` files. To port:

1. **Operating manual** — Cursor reads `AGENTS.md` natively (since Cursor 0.45+). The shipped `AGENTS.md` is sufficient.
2. **Sub-agents** — convert each `.claude/agents/*.md` to a `.cursor/rules/*.mdc` rule. The frontmatter `name` and `description` map directly. Pin each rule to "agent-only" mode if Cursor offers that.
3. **Skills** — Cursor doesn't have a slash-command equivalent. Treat skills as additional rules invoked when the user types the name in chat.
4. **Sandbox** — use Cursor's `.cursorignore` to limit filesystem visibility. Note: this is a soft restriction; Cursor's permission system is less strict than Claude Code's.

### Aider

Aider reads `CONVENTIONS.md` by default (configurable via `--read`). To port:

1. Point Aider at `AGENTS.md`:

```bash
aider --read AGENTS.md --read DOMAIN.md --read USER_PREFERENCES.md
```

2. Load the FORRT reference material when working on nanopub drafts:

```bash
aider --read docs/forrt-form-fields.md --read docs/chain-decision-tree.md
```

3. Sub-agents and skills don't have direct equivalents. Use the relevant `.claude/agents/*.md` body as an Aider system prompt for that phase of work.

### Continue (VS Code / JetBrains)

Continue uses `.continue/config.json`. To port:

1. Add the operating manual to the system prompt:

```json
{
  "systemMessage": "You are working on a FORRT replication study. Read CLAUDE.md, DOMAIN.md, and USER_PREFERENCES.md at the start of every session. The full operating manual is in CLAUDE.md."
}
```

2. Add per-phase prompts (paper analysis, code port, nanopub drafting) as separate Continue commands invoking the relevant `docs/` and `.claude/agents/` content.

### OpenAI Codex / GPT-based agents

Treat `AGENTS.md` as the system prompt for the session. Load `docs/forrt-form-fields.md` and the chain-related docs into context when entering Phase 5.

For programmatic agents, the standard pattern is:

```python
SYSTEM_PROMPT = open("AGENTS.md").read() + open("DOMAIN.md").read() + open("USER_PREFERENCES.md").read()
```

…then load `docs/<relevant>.md` per task.

### Generic IDE chat (no project file awareness)

If your AI tool can't read project files, manually paste:

1. `AGENTS.md` (one-time, at session start) — establishes operating rules.
2. `DOMAIN.md` (one-time) — domain conventions.
3. The relevant `docs/*.md` per task — e.g. `docs/forrt-form-fields.md` when drafting nanopubs.

## Common pitfalls

### "The AI doesn't know about the imports"

If the AI tool doesn't auto-resolve `@DOMAIN.md` `@USER_PREFERENCES.md` imports in `CLAUDE.md`, the operating manual will be missing the domain and user-preference layers. **Tell the AI explicitly at session start:** *"Before any other action, read `CLAUDE.md`, then read `DOMAIN.md` and `USER_PREFERENCES.md`. Apply the rules from all three."*

### "The AI is editing files outside the repo"

If the AI doesn't honour `.claude/settings.json` (i.e. it's not Claude Code), use the AI tool's own permission system. For Cursor, `.cursorignore`. For Aider, run inside a `chroot` or container. For others, consult the tool's docs.

If no permission system is available, monitor file edits manually — review every change before accepting it. The sandbox is *belt-and-braces*, not a strict guarantee.

### "Skills are inert"

Skills (`.claude/skills/*/SKILL.md`) are Claude Code-specific. Other AIs see the markdown but won't auto-invoke them on `/skill-name` typing. Either:

- Manually copy the skill body into the session when needed.
- Convert each skill to your tool's equivalent (Cursor rule, Aider system-prompt block, etc.).

### "How do I run the init-template flow without Claude Code?"

`/init-template` is a Claude Code skill. For other AIs, the equivalent procedure is:

1. Find all `{{...}}` placeholder tokens (`grep -r '{{[A-Z_]\+}}' .`).
2. Substitute them by hand or with a `sed` script — the SKILL.md body documents which token goes where.
3. Configure git identity per `USER_PREFERENCES.md`.
4. Commit and push.
5. Delete `.claude/skills/init-template/` so the new repo doesn't ship template-bootstrap artefacts.

The full procedure is documented in `.claude/skills/init-template/SKILL.md` — a non-Claude AI can read and follow it manually.

## Long-term direction

The cross-AI [`AGENTS.md` convention](https://agents.md/) is converging across major AI coding tools. As that consolidates, more of the Claude-specific scaffolding here will become directly portable. For now, the dual-file approach (`CLAUDE.md` + `AGENTS.md`, identical content) is the most robust way to support both ecosystems.

If your team standardises on a non-Claude tool, you can:

1. Delete `CLAUDE.md` and the `.claude/` directory entirely.
2. Move the operating-manual content into `AGENTS.md`.
3. Replace `.claude/agents/*.md` with your tool's equivalent.

The template's portable core (`docs/`, `DOMAIN.md`, `USER_PREFERENCES.md`, `nanopubs/drafts/`, the boilerplate files, the workflows) is unchanged.

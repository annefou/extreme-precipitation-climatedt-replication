# AGENTS.md — operating manual for AI assistants

This file is the cross-AI operating manual for this replication study. It exists alongside `CLAUDE.md` (Claude Code's preferred filename) so that Cursor, Aider, Continue, OpenAI Codex, and other AI tooling that reads `AGENTS.md` get the same operating context.

The two files share content. Read whichever your tool picks up. If your tool reads `AGENTS.md`, also follow the imports declared at the top of `CLAUDE.md` — `DOMAIN.md` and `USER_PREFERENCES.md` — by reading them at the start of each session.

For the actual operating instructions, read [CLAUDE.md](CLAUDE.md). It is the single source of truth.

## AI portability — what works in your tool

| AI tool | Reads | What translates |
|---|---|---|
| Claude Code | `CLAUDE.md` (with `@`-imports) | Everything: `CLAUDE.md`, `DOMAIN.md`, `USER_PREFERENCES.md`, `.claude/agents/`, `.claude/skills/`, `.claude/settings.json` |
| Cursor | `.cursor/rules/*.mdc` and `AGENTS.md` | `CLAUDE.md` content via `AGENTS.md`. Convert `.claude/agents/*.md` to `.cursor/rules/*.mdc` if you want them. Skills aren't natively supported. |
| Aider | `CONVENTIONS.md` (configurable) | Point Aider at `AGENTS.md` via `--read AGENTS.md`. |
| Continue | `.continue/config.json` system prompts | Paste relevant sections of `AGENTS.md` into the system prompt. |
| OpenAI Codex / GPT-based agents | tool-specific | Read `AGENTS.md` at session start; load `docs/` reference material on demand. |
| Generic IDE chat (no project files) | clipboard | Manually paste `AGENTS.md` plus the relevant `docs/` sections. |

The portable, content-only artefacts — readable by any AI — are:

- `CLAUDE.md` / `AGENTS.md` (operating manual, identical content)
- `DOMAIN.md` (domain conventions)
- `USER_PREFERENCES.md` (user style)
- `docs/*.md` (reference material)
- `nanopubs/drafts/*.md` (draft scaffolds)

The Claude-specific artefacts — only Claude Code uses them as-is — are:

- `.claude/agents/` (specialist sub-agents — paper-analyst, replication-coder, nanopub-drafter)
- `.claude/skills/` (slash commands — `/init-template`, `/replication-study`)
- `.claude/settings.json` (sandbox permissions)

These can be ported to other tools by copying the prompts inside them and registering them via that tool's mechanism (Cursor rules, Aider system prompts, etc.). See [`docs/ai-portability.md`](docs/ai-portability.md) for the full mapping.

## A note on the sandbox

`CLAUDE.md` mentions a sandbox enforced by `.claude/settings.json` that restricts file ops to the repository directory. **Other AI tools have their own permission systems.** When using Cursor, Aider, etc., consult that tool's permission documentation if you want to constrain file access; the `.claude/settings.json` file does not apply to them.

The intent of the sandbox is *"the AI should only be able to read and write files inside this repository"*. If your tool has a way to enforce that, do so. If not, be aware that the AI may have broader access than intended.

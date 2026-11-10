# Claude model reference

As of 2026-11-09. Source: [Which Claude model should you build with?](https://claude.dev/blog/which-claude-model-should-you-build-with/). These numbers age quickly, so check [choosing a model](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model) when a decision depends on them.

## Current models

| | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Fable 5.2 |
| --- | --- | --- | --- | --- |
| Best for | High-volume, cost-sensitive work | Scoped tasks | Daily complex work | Hardest open-ended technical work |
| Input / output per MTok | $0.10 / $0.50 up to 100K prompt, $0.50 / $2.50 above | $2 / $10 | $4 / $20 | $8 / $40 |
| Cache read per MTok | $0.01 up to 100K, $0.05 above | $0.10 | $0.20 | $0.20 |
| Default effort, API | `medium` | `high` | `medium` | `high` |
| Default effort, Claude Code | `medium` | `medium` | `medium` | `medium` |
| Thinking | On, can be turned off | On, `between_tools` limits it | Always on | Always on |
| Fast mode | No | No | Yes | Yes |

All four have a 1M-token context window and 128K max output. Claude Mythos 5.2 exists for cybersecurity and life sciences research, through verification programs only.

The `haiku` alias resolves to Haiku 5.5 on the Anthropic API from Claude Code v2.1.293. On Bedrock, Google Cloud, Microsoft Foundry, and Claude Platform on AWS it still resolves to Haiku 4.5. Pin it with `ANTHROPIC_DEFAULT_HAIKU_MODEL`.

## Cost signals

- Opus `medium` costs about 70% of `high` on SWE-bench Pro for about 2.5 points less. `low` costs about a third for about 8 points less. `xhigh` costs 2.5 times `high` for about 1.4 points more.
- Fable at `high` matched Opus at `max` on FrontierCode 2.0 at about half the cost per task, so test Fable before pushing Opus past `high`.
- Opus at `low` with failures re-run at `high` passed about 97% at $0.17 per task, against 95.3% at $0.29 for everything at `high`, on a SWE-bench Pro subset.
- Haiku is the only model priced by prompt length. For long prompts, compare it with Sonnet on cost per finished task.
- Context is resent every turn. Most long-run input bills as cache reads.

## Multi-model patterns

- Keep one model per step type and let code route when routing is simple.
- `opusplan` puts code edits on Sonnet, which is the reverse of the usual advice. Measure before making it a default.
- The advisor tool (beta) pairs a cheaper executor with a stronger advisor. Most published pairings did not clearly beat the executor alone.
- For work larger than one context window, an Opus lead over parallel Sonnet workers cost about a third less than Opus alone at about the same score. Skip it for one dependent chain or work that fits one window.

## API compatibility

Build multi-model systems for the strictest model.

- Keep history append-only. Fable 5.2 returns 400 if anything before one of its thinking blocks changed, unless you opt in to dropping the affected thinking.
- Read content blocks by `type`, since a response can start with a thinking block.
- `tool_choice` of `any` or `tool` returns 400 on Sonnet 5.5, Opus 5.5, and Fable 5.2. Send `auto`, mark tools `strict: true`, and say in the prompt when to use them.
- Opus 5.5 and Fable 5.2 error if thinking is turned off. Haiku 5.5 allows it at `high` effort or below.
- Computer use on current models needs the `computer_toolset_20260801` toolset.
- Haiku 4.5 to 5.5: replace `budget_tokens` with effort, drop non-default `temperature`, `top_p`, and `top_k`, and end `messages` with a user turn.
- Safety classifiers can re-run a flagged request on an older model, most often for cybersecurity and biology.

## Evaluating a choice

1. Sample real tasks and write an outcome check for each.
2. Run each candidate at two or three effort levels, in separate sessions so runs don't share cache. Record cost from `usage`.
3. Plot score against spend. Keep a multi-model setup only if it beats every single-model point.
4. Shadow-run the winner on real traffic before cutover.

For a quick check in Claude Code, run one backlog task on two models and compare `/usage`.

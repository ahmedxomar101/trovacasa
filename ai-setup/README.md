# AI-Assisted Setup

TrovaCasa can be configured manually by editing `config.yaml`, or with the help of an AI coding assistant (Claude Code, Cursor, GitHub Copilot, etc.).

## How It Works

Each file below contains a structured prompt. Copy its contents and paste it into your AI assistant's chat. The assistant will walk you through the setup interactively, asking questions and generating the correct files.

## Setup Prompts

| Prompt | What It Does | When to Use |
|--------|-------------|-------------|
| `config-builder.md` | Generates your `config.yaml` | First-time setup |
| `city-builder.md` | Creates metro + neighborhood data for a new city | Your city isn't in `data/cities/` |
| `scoring-builder.md` | Customizes scoring weights, thresholds, or adds custom scorers | You want to tune how listings are ranked |

## Recommended Order

1. Check if your city is supported: look in `pipeline/data/cities/`
2. If not, run **city-builder** first
3. Run **config-builder** to generate your `config.yaml`
4. Optionally run **scoring-builder** to fine-tune ranking

## Validation

After setup, always validate your configuration:

```bash
cd pipeline && uv run python -m src.main validate
```

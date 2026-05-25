# Hermes Command Code Provider

A Hermes provider bridge for using Hermes Agent with a Command Code Go
subscription.

## Why this exists

Command Code Go subscriptions can authenticate the Command Code CLI, but they do
not include direct access to the Command Code provider API. This plugin works
around that limitation for personal Hermes usage by running a local
OpenAI-compatible bridge backed by your existing Command Code subscription
login.

Chinese explanation: [为什么 Go 订阅可以这样使用](WHY_GO_SUBSCRIPTION_WORKS.zh-CN.md).

This project provides:

- a Hermes `model-provider` plugin named `commandcode`
- a local OpenAI-compatible bridge at `http://127.0.0.1:8788/v1`
- model metadata with `context_length` so Hermes context usage displays correctly
- streaming `usage` chunks so Hermes updates token/session statistics
- tool-call translation between OpenAI Chat Completions and Command Code events

## Requirements

- macOS or Linux
- Hermes Agent v0.14.0 or newer
- `curl`
- Python 3
- a Command Code login or API key

Authenticate with Command Code first:

```bash
cmd login
```

Or export an API key:

```bash
export COMMANDCODE_API_KEY="..."
```

The bridge also reads `~/.commandcode/auth.json` and `~/.pi/agent/auth.json`.

## Install

```bash
git clone https://github.com/MitoroMisaka/hermes-commandcode-provider.git
cd hermes-commandcode-provider
./install.sh --configure
```

`install.sh` copies the provider plugin, bridge, and helper command into your
Hermes home. With `--configure`, it also updates `~/.hermes/config.yaml` and
backs it up first. It also applies small Hermes compatibility patches for
Command Code:

- the model picker counts model-provider plugin fallback models correctly
- `hermes doctor` accepts Command Code slash-form model ids

## Use

Start Hermes normally after configuration:

```bash
hermes
```

Or run a one-shot test:

```bash
hermes -z 'Reply with exactly OK.'
```

You can also use the helper, which starts the local bridge before running Hermes:

```bash
hermes-commandcode -z 'Reply with exactly OK.'
```

Switch models explicitly:

```bash
hermes --provider commandcode -m moonshotai/Kimi-K2.5 -z 'Reply with exactly OK.'
hermes --provider commandcode -m deepseek/deepseek-v4-flash -z 'Reply with exactly OK.'
```

## Supported Models

The bridge exposes the live Command Code `/provider/v1/models` catalog when
available, and falls back to a bundled catalog. Known context windows include:

| Model | Context |
| --- | ---: |
| `moonshotai/Kimi-K2.6` | 256000 |
| `moonshotai/Kimi-K2.5` | 256000 |
| `deepseek/deepseek-v4-flash` | 1000000 |
| `deepseek/deepseek-v4-pro` | 1000000 |
| `claude-sonnet-4-6` | 1000000 |
| `claude-opus-4-7` | 1000000 |
| `gpt-5.4` | 400000 |

## Smoke Test

```bash
./scripts/smoke_test.sh
```

The smoke test checks:

- `/v1/models` returns model metadata and context lengths
- non-streaming chat works
- streaming chat returns a final `usage` chunk
- tool calls are translated correctly

## Hermes Doctor Note

Some Hermes versions warn that slash-form model ids such as
`moonshotai/Kimi-K2.5` are "vendor-prefixed" and should belong to aggregators.
Command Code legitimately uses these ids.

If your Hermes version shows that warning, either ignore it or run:

```bash
./scripts/patch_doctor.py
```

The patch only adds `commandcode` to the doctor allowlist for slash-form model ids.

## Model Picker Note

Some Hermes versions auto-discover user-installed model-provider plugins but do
not count their `fallback_models` on the first provider picker screen. In that
case, Command Code can show as `0 models` even though opening it displays the
models and switching works.

Run this compatibility patch if needed:

```bash
./scripts/patch_model_picker.py
```

The patch only teaches the provider overview to count fallback models declared
by installed model-provider plugins.

## Files Installed

```text
~/.hermes/commandcode_proxy.py
~/.hermes/plugins/model-providers/commandcode/__init__.py
~/.hermes/plugins/model-providers/commandcode/plugin.yaml
~/.local/bin/hermes-commandcode
```

No token is written into this repository. The bridge reads your existing
Command Code auth at runtime.

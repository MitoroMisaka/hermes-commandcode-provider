"""Command Code provider profile for the local Go subscription bridge."""

from providers import register_provider
from providers.base import OMIT_TEMPERATURE, ProviderProfile


commandcode = ProviderProfile(
    name="commandcode",
    aliases=("command-code", "commandcode-alpha", "cc"),
    display_name="Command Code",
    description="Command Code Go subscription via local OpenAI-compatible bridge",
    signup_url="https://commandcode.ai/",
    env_vars=("COMMANDCODE_API_KEY",),
    base_url="http://127.0.0.1:8788/v1",
    models_url="http://127.0.0.1:8788/v1/models",
    auth_type="api_key",
    fixed_temperature=OMIT_TEMPERATURE,
    default_max_tokens=32000,
    default_aux_model="moonshotai/Kimi-K2.5",
    fallback_models=(
        "claude-sonnet-4-6",
        "claude-opus-4-7",
        "claude-haiku-4-5-20251001",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.3-codex",
        "gpt-5.4-mini",
        "moonshotai/Kimi-K2.6",
        "moonshotai/Kimi-K2.5",
        "zai-org/GLM-5.1",
        "zai-org/GLM-5",
        "MiniMaxAI/MiniMax-M2.7",
        "MiniMaxAI/MiniMax-M2.5",
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v4-flash",
        "Qwen/Qwen3.6-Max-Preview",
        "Qwen/Qwen3.6-Plus",
        "Qwen/Qwen3.7-Max",
        "stepfun/Step-3.5-Flash",
        "xiaomi/mimo-v2.5-pro",
        "xiaomi/mimo-v2.5",
        "google/gemini-3.5-flash",
        "google/gemini-3.1-flash-lite",
    ),
)


register_provider(commandcode)

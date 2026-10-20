"""Compatibility entrypoint backed by the validated multi-provider client."""
import os

from multi_llm_client import call_gemini, load_config

# Credentials are supplied by environment or api_config.json, never source code.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-3.7-flash"
MODEL_POOL = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3-flash-preview"]


def ask_gemini(prompt, system_instruction=None, model=DEFAULT_MODEL, temperature=0.7,
               max_retries=6, return_usage=False, thinking_budget=1500):
    """Return a complete final answer; optionally include usage and model provenance.

    Legacy model fallback is restricted to the configured Gemini model list when
    present. Semantic pipeline roles should use ask_ai(role=...) instead.
    """
    config = load_config()
    provider_cfg = dict(config.get("providers", {}).get("gemini", {}))
    key = os.environ.get("GEMINI_API_KEY") or GEMINI_API_KEY
    if key:
        provider_cfg["api_keys"] = [key]
    configured_models = provider_cfg.get("models")
    if configured_models is not None:
        # Honor deployment policy instead of adding unconfigured legacy models.
        if model in configured_models:
            provider_cfg["models"] = [model] + [m for m in configured_models if m != model]
    else:
        provider_cfg["models"] = [model] + [m for m in MODEL_POOL if m != model]
    provider_cfg.update({"temperature": temperature, "thinking_budget": thinking_budget})
    settings = dict(config.get("settings", {}))
    settings["max_retries"] = max_retries
    text, usage, _ = call_gemini(prompt, system_instruction, provider_cfg, settings)
    return (text, usage) if return_usage else text


if __name__ == "__main__":
    print(ask_gemini("Hãy phản hồi: Gemini đã sẵn sàng phục vụ!"))

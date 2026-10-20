import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import re
import random
import urllib.request
import urllib.error

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.json")


class IncompleteResponseError(ValueError):
    """The provider did not return a complete, nonempty final answer."""


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _retry_count(settings):
    count = settings.get("max_retries", 5)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("max_retries phải là số nguyên dương.")
    return count


def _models(provider_cfg, default):
    models = provider_cfg.get("models", default)
    if not isinstance(models, list) or not models or any(
        not isinstance(m, str) or not m.strip() for m in models
    ):
        raise ValueError("models phải là danh sách tên model không rỗng.")
    return list(dict.fromkeys(models))


def _usage(metadata, provider, requested_model, reported_model, finish_reason):
    usage = dict(metadata) if isinstance(metadata, dict) else {}
    usage.update({
        "provider": provider,
        "requested_model": requested_model,
        "model_used": reported_model or requested_model,
        "model_reported": bool(reported_model),
        "finish_reason": finish_reason,
    })
    return usage


def _final_answer_text(text):
    # Some compatible reasoners embed thought blocks in content instead of a
    # separate reasoning field. Remove complete blocks; reject unclosed ones.
    for tag in ("think", "analysis"):
        text = re.sub(rf"<{tag}>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)
        if re.search(rf"</?{tag}>", text, flags=re.IGNORECASE):
            raise IncompleteResponseError("Provider trả về khối suy luận chưa hoàn chỉnh.")
    return text.strip()


def _gemini_response(data, requested_model):
    candidates = data.get("candidates", [])
    if not candidates or not isinstance(candidates[0], dict):
        raise IncompleteResponseError("Gemini không trả về câu trả lời hoàn chỉnh.")
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    if finish_reason != "STOP":
        raise IncompleteResponseError("Gemini kết thúc không thành công hoặc bị cắt ngắn.")
    parts = candidate.get("content", {}).get("parts", [])
    texts = [p["text"] for p in parts if isinstance(p, dict)
             and not p.get("thought", False) and isinstance(p.get("text"), str)]
    answer = _final_answer_text("".join(texts))
    if not answer:
        raise IncompleteResponseError("Gemini trả về nội dung cuối rỗng.")
    usage = _usage(data.get("usageMetadata"), "gemini", requested_model,
                   data.get("modelVersion"), finish_reason)
    return answer, usage, f"gemini/{usage['model_used']}"


def _openai_response(data, provider, requested_model):
    choices = data.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        raise IncompleteResponseError("Provider không trả về câu trả lời hoàn chỉnh.")
    choice = choices[0]
    finish_reason = choice.get("finish_reason")
    if finish_reason != "stop":
        raise IncompleteResponseError("Provider kết thúc không thành công hoặc bị cắt ngắn.")
    message = choice.get("message", {})
    answer = message.get("content")
    if message.get("refusal") or not isinstance(answer, str) or not answer.strip():
        raise IncompleteResponseError("Provider trả về nội dung rỗng hoặc từ chối.")
    answer = _final_answer_text(answer)
    if not answer:
        raise IncompleteResponseError("Provider chỉ trả về nội dung suy luận.")
    usage = _usage(data.get("usage"), provider, requested_model,
                   data.get("model"), finish_reason)
    return answer, usage, f"{provider}/{usage['model_used']}"


def call_gemini(prompt, system_instruction, provider_cfg, settings):
    api_keys = provider_cfg.get("api_keys", [])
    if not isinstance(api_keys, list) or not api_keys or any(
        not isinstance(key, str) or not key.strip() or "YOUR_" in key for key in api_keys
    ):
        raise ValueError("Chưa cấu hình api_keys hợp lệ cho provider 'gemini'.")
    models = _models(provider_cfg, ["gemini-3.7-flash", "gemini-3.6-flash"])
    temperature = provider_cfg.get("temperature", 0.7)
    thinking_budget = provider_cfg.get("thinking_budget", 1500)
    max_retries = _retry_count(settings)
    backoff_delays = [2, 4, 8, 12, 16]

    for current_model in models:
        for current_key in api_keys:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
            gen_config = {"temperature": temperature}
            if thinking_budget is not None and thinking_budget >= 0:
                gen_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": gen_config,
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-goog-api-key": current_key},
            )
            for attempt in range(max_retries):
                try:
                    with urllib.request.urlopen(req, timeout=settings.get("timeout", 90)) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    return _gemini_response(data, current_model)
                except IncompleteResponseError:
                    print(f"[*] [Gemini - {current_model}] Đầu ra chưa hoàn chỉnh; từ chối kết quả.")
                    break
                except urllib.error.HTTPError as exc:
                    # Inspect quota/retry fields without logging response bodies or URLs.
                    err_msg = exc.read().decode("utf-8", errors="ignore")
                    daily_limit = any(s in err_msg for s in (
                        "limit: 20", "PerDay", "generate_content_free_tier_requests"))
                    if exc.code == 429 and daily_limit:
                        print(f"[*] [Gemini - {current_model}] Hết quota ngày; thử cấu hình kế tiếp.")
                        break
                    if exc.code in (429, 503) and attempt < max_retries - 1:
                        delay_match = re.search(r'Please retry in ([0-9.]+)s', err_msg)
                        suggested_delay = (float(delay_match.group(1)) + 2.0 if delay_match
                                           else backoff_delays[min(attempt, len(backoff_delays) - 1)]
                                           + random.uniform(1.0, 3.0))
                        if suggested_delay > 20.0:
                            print(f"[*] [Gemini - {current_model}] Chờ quota quá lâu; thử cấu hình kế tiếp.")
                            break
                        print(f"[*] [Gemini - {current_model}] HTTP {exc.code}; thử lại sau {suggested_delay:.1f}s.")
                        time.sleep(suggested_delay)
                        continue
                    print(f"[*] [Gemini - {current_model}] HTTP {exc.code}; yêu cầu thất bại.")
                    break
                except Exception:
                    print(f"[*] [Gemini - {current_model}] Lỗi kết nối hoặc định dạng phản hồi.")
                    if attempt < max_retries - 1:
                        time.sleep(backoff_delays[min(attempt, len(backoff_delays) - 1)])
                        continue
                    break
    raise RuntimeError("Tất cả models/keys của Gemini đều thất bại.") from None


def call_openai_compatible(prompt, system_instruction, provider_name, provider_cfg, settings):
    api_key = provider_cfg.get("api_key", "")
    if not isinstance(api_key, str) or not api_key.strip() or "YOUR_" in api_key:
        raise ValueError("Chưa cấu hình api_key hợp lệ cho provider.")
    base_url = provider_cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
    models = _models(provider_cfg, ["gpt-4o-mini"])
    temperature = provider_cfg.get("temperature", 0.7)
    max_retries = _retry_count(settings)
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    for current_model in models:
        payload = {"model": current_model, "messages": messages, "temperature": temperature}
        req = urllib.request.Request(
            f"{base_url}/chat/completions", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=settings.get("timeout", 120)) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return _openai_response(data, provider_name, current_model)
            except IncompleteResponseError:
                print(f"[*] [{provider_name} - {current_model}] Đầu ra chưa hoàn chỉnh; từ chối kết quả.")
                break
            except urllib.error.HTTPError as exc:
                print(f"[*] [{provider_name} - {current_model}] HTTP {exc.code}; yêu cầu thất bại.")
                if exc.code in (429, 503) and attempt < max_retries - 1:
                    time.sleep(5 + attempt * 3)
                    continue
                break
            except Exception:
                print(f"[*] [{provider_name} - {current_model}] Lỗi kết nối hoặc định dạng phản hồi.")
                if attempt < max_retries - 1:
                    time.sleep(3 + attempt * 2)
                    continue
                break
    raise RuntimeError("Tất cả models của provider đều thất bại.") from None


def ask_ai(prompt, system_instruction=None, preferred_provider=None, role=None):
    """Unified entrypoint; role selection requires explicit provider and models.

    quality_roles[role] = {"provider": "gemini", "models": ["model-id"]}.
    A role can try only its explicitly configured models, without provider fallback.
    """
    config = load_config()
    settings = config.get("settings", {})
    providers = config.get("providers", {})
    role_cfg = None
    if role is not None:
        role_cfg = config.get("quality_roles", {}).get(role)
        if not isinstance(role_cfg, dict):
            raise ValueError("Vai trò chất lượng chưa được cấu hình trong quality_roles.")
        active_provider = role_cfg.get("provider")
        if not isinstance(active_provider, str) or active_provider not in providers:
            raise ValueError("Provider của vai trò chất lượng chưa được cấu hình.")
        if preferred_provider and preferred_provider != active_provider:
            raise ValueError("preferred_provider xung đột với provider của vai trò chất lượng.")
        _models(role_cfg, [])
        providers_to_try = [active_provider]
    else:
        active_provider = preferred_provider or config.get("active_provider", "gemini")
        providers_to_try = [active_provider]
        if settings.get("auto_fallback_provider", True):
            for name, provider in providers.items():
                if name != active_provider and (provider.get("api_key") or provider.get("api_keys")):
                    providers_to_try.append(name)

    for provider_name in providers_to_try:
        provider_cfg = dict(providers.get(provider_name, {}))
        if role_cfg is not None:
            provider_cfg["models"] = list(role_cfg["models"])
            for option in ("temperature", "thinking_budget"):
                if option in role_cfg:
                    provider_cfg[option] = role_cfg[option]
        try:
            if provider_name == "gemini":
                return call_gemini(prompt, system_instruction, provider_cfg, settings)
            return call_openai_compatible(prompt, system_instruction, provider_name, provider_cfg, settings)
        except Exception:
            # Never interpolate exceptions: URLError/HTTPError may contain credentials.
            print(f"[*] Provider '{provider_name}' không hoàn tất yêu cầu.")
    raise RuntimeError("Các providers được phép không thể hoàn tất yêu cầu.") from None


if __name__ == "__main__":
    print("[*] Kiểm tra kết nối AI Client theo api_config.json...")
    res, usage, model_used = ask_ai("Xin chào! Hãy phản hồi ngắn gọn: Hệ thống Multi-Provider đã sẵn sàng!")
    print(f"[{model_used}] -> {res}")

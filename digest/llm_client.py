import json
import logging
import os
import re
import time
from collections import defaultdict

from openai import OpenAI

from digest.parser import Config
from digest.prompt_loader import render_prompt

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    if not text:
        return text
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def get_light_client():
    config_obj = Config("config/config.yaml")
    cfg = config_obj.get("llm", {}).get("light", {})
    api_key = cfg.get("api_key") or os.environ.get("SILICONFLOW_API_KEY")
    base_url = cfg.get("base_url", "https://api.siliconflow.cn/v1")
    model = cfg.get("model", "Qwen/Qwen3-8B")
    return OpenAI(api_key=api_key, base_url=base_url), model


_MODEL_UNAVAILABLE_PHRASES = [
    "is no longer available",
    "has been deprecated",
    "model not found",
    "does not exist",
]


def _is_bad_response(content: str, min_chars: int) -> tuple[bool, str]:
    lower = content.lower()
    for phrase in _MODEL_UNAVAILABLE_PHRASES:
        if phrase in lower:
            return True, f"model unavailable signal: '{phrase}'"
    if len(content) < min_chars:
        return True, f"response too short ({len(content)} chars < {min_chars} threshold)"
    return False, ""


def get_heavy_client():
    config_obj = Config("config/config.yaml")
    cfg = config_obj.get("llm", {}).get("heavy", {})
    api_key = cfg.get("api_key") or os.environ.get("LOCAL_API_KEY")
    base_url = cfg.get("base_url", os.environ.get("LOCAL_BASE_URL", "http://localhost:3000/v1"))
    model = cfg.get("model", "gpt")
    fallback_models = cfg.get("fallback_models", [])
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model, fallback_models


def call_with_retry(client, model, messages, max_retries=3, fallback_models=None, min_chars=0, **kwargs):
    models_to_try = [model] + (fallback_models or [])

    for current_model in models_to_try:
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                response = client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                    **kwargs,
                )
                duration = time.time() - start_time
                content = response.choices[0].message.content

                bad, reason = _is_bad_response(content, min_chars)
                if bad:
                    logger.warning("Model %s bad response (%s), trying next fallback", current_model, reason)
                    break

                if current_model != model:
                    logger.info("API Call (%s) [fallback from %s]: %.2fs", current_model, model, duration)
                else:
                    logger.info("API Call (%s): %.2fs", current_model, duration)
                return content
            except Exception as e:
                logger.warning("API Error (%s, attempt %s): %s", current_model, attempt + 1, e)
                time.sleep(2**attempt)

    logger.error("All models exhausted: %s", models_to_try)
    return None


def filter_important_articles(articles: list[dict]) -> list[dict]:
    logger.info("Step 1: Filtering %s articles (target: keep 50-60%%)...", len(articles))
    client, model = get_light_client()
    selected_indices = []
    batch_size = 20

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        titles = [
            {"id": j, "title": a.get("title", ""), "source": a.get("source", "")}
            for j, a in enumerate(batch)
        ]
        prompt = render_prompt("filter_important_articles", titles_json=json.dumps(titles, ensure_ascii=False, indent=2))
        result = call_with_retry(
            client,
            model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            if result:
                data = json.loads(_extract_json(result))
                for lid in data.get("selected_ids", []):
                    if 0 <= lid < len(batch):
                        selected_indices.append(i + lid)
        except Exception as e:
            logger.error("Filter parse error: %s", e)

    selected = [articles[i] for i in selected_indices]
    logger.info("Total selected: %s articles", len(selected))
    return selected


def categorize_articles(articles: list[dict]) -> dict[str, list[dict]]:
    logger.info("Step 2: Categorizing articles...")
    client, model = get_light_client()
    categorized = defaultdict(list)
    titles = [{"id": i, "title": a.get("title", "")} for i, a in enumerate(articles)]

    for i in range(0, len(titles), 20):
        batch = titles[i : i + 20]
        prompt = render_prompt("categorize_articles", titles_json=json.dumps(batch, ensure_ascii=False))
        result = call_with_retry(
            client,
            model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        try:
            if result:
                mapping = json.loads(_extract_json(result))
                for cat, ids in mapping.items():
                    for lid in ids:
                        lid_int = int(lid) if isinstance(lid, (int, str)) and str(lid).isdigit() else None
                        if lid_int is not None and 0 <= lid_int < len(articles):
                            categorized[cat].append(articles[lid_int])
        except Exception as e:
            logger.error("Categorize error: %s", e)

    valid_cats = ["科技前沿", "商业产业", "经济股市", "政策政治", "社会民生", "国际新闻", "文化娱乐"]
    final_categorized = {k: v for k, v in categorized.items() if k in valid_cats and v}
    logger.info("Categories: %s", list(final_categorized.keys()))
    return final_categorized


def write_deep_summary(category: str, articles: list[dict]) -> str:
    client, model, fallback_models = get_heavy_client()
    context = ""
    for article in articles:
        content_preview = (article.get("content") or "")[:1200]
        context += (
            f"标题：{article.get('title')}\n"
            f"来源：{article.get('source')}\n"
            f"链接：{article.get('link')}\n"
            f"正文：{content_preview}\n\n---\n\n"
        )

    logger.info("Writing summary for %s (%s arts, ~%s chars)...", category, len(articles), len(context))
    prompt = render_prompt("write_deep_summary", category=category, context=context)
    result = call_with_retry(
        client,
        model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=32768,
        fallback_models=fallback_models,
        min_chars=200,
    )
    return result or ""


def generate_three_points(summary_text: str) -> str:
    client, model, fallback_models = get_heavy_client()
    prompt = render_prompt("generate_three_points", summary_text=summary_text)
    result = call_with_retry(
        client,
        model,
        messages=[{"role": "user", "content": prompt}],
        fallback_models=fallback_models,
        min_chars=50,
    )
    return result or ""

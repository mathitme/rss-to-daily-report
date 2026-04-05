#!/usr/bin/env python3
import argparse
import glob
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from digest.llm_client import call_with_retry, get_heavy_client, get_light_client  # noqa: E402
from digest.parser import MarkdownParser  # noqa: E402
from digest.prompt_loader import render_prompt  # noqa: E402
from digest.runtime import ensure_runtime_directories, get_runtime_paths  # noqa: E402


FINANCE_CATEGORIES = [
    "美股/A 股",
    "宏观经济",
    "金融监管",
    "市场行情",
    "企业财报",
    "债券市场",
    "商品期货",
    "货币政策",
]


def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def get_date_directories(base_path, hours=36, reference_now=None):
    if reference_now is None:
        reference_now = datetime.now()
    cutoff_time = reference_now - timedelta(hours=hours)

    directories = []
    current_date = cutoff_time.date()
    end_date = reference_now.date()
    while current_date <= end_date:
        date_path = os.path.join(
            base_path,
            str(current_date.year),
            f"{current_date.month:02d}",
            f"{current_date.day:02d}",
        )
        if os.path.exists(date_path):
            directories.append(date_path)
        current_date += timedelta(days=1)
    return directories


def parse_article_date(date_str):
    if not date_str or date_str == "Unknown":
        return None

    date_str = date_str.strip()
    try:
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is not None:
            import zoneinfo

            local_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
            dt = dt.astimezone(local_tz).replace(tzinfo=None)
        return dt
    except (ValueError, ImportError):
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def filter_theme_articles(articles: list[dict], theme: str, theme_description: str) -> list[dict]:
    logger = logging.getLogger(__name__)
    logger.info("Filtering %s articles for theme: %s", len(articles), theme)

    client, model = get_light_client()
    selected_indices = []
    batch_size = 50 if len(articles) > 500 else 40 if len(articles) > 100 else 20

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        titles = [
            {"id": j, "title": a.get("title", ""), "source": a.get("source", "")}
            for j, a in enumerate(batch)
        ]
        prompt = render_prompt(
            "filter_theme_articles",
            theme=theme,
            theme_description=theme_description,
            titles_json=json.dumps(titles, ensure_ascii=False, indent=2),
        )
        result = call_with_retry(
            client,
            model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            if result:
                data = json.loads(result)
                for lid in data.get("selected_ids", []):
                    if 0 <= lid < len(batch):
                        selected_indices.append(i + lid)
        except Exception as e:
            logger.error("Theme filter parse error: %s", e)

    selected = [articles[i] for i in selected_indices]
    logger.info("Theme '%s': selected %s/%s articles", theme, len(selected), len(articles))
    return selected


def _categorize_finance_batch(batch_articles: list[dict], client, model, logger) -> dict[str, list[dict]]:
    categorized = defaultdict(list)
    titles = [
        {"id": i, "title": a.get("title", ""), "source": a.get("source", "")}
        for i, a in enumerate(batch_articles)
    ]
    prompt = render_prompt(
        "categorize_finance_batch",
        categories_str="、".join(FINANCE_CATEGORIES),
        titles_json=json.dumps(titles, ensure_ascii=False),
    )

    result = call_with_retry(
        client,
        model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    if not result:
        return categorized

    try:
        mapping = json.loads(result)
        assigned_ids = set()
        for cat, ids in mapping.items():
            if not isinstance(ids, list):
                continue
            for lid in ids:
                lid_int = int(lid) if isinstance(lid, (int, str)) and str(lid).isdigit() else None
                if lid_int is not None and 0 <= lid_int < len(batch_articles) and lid_int not in assigned_ids:
                    categorized[cat].append(batch_articles[lid_int])
                    assigned_ids.add(lid_int)
    except json.JSONDecodeError as e:
        logger.warning("Finance category parse error: %s", e)

    return categorized


def dynamic_subcategorize(articles: list[dict], theme: str) -> dict[str, list[dict]]:
    logger = logging.getLogger(__name__)
    logger.info("Categorizing %s articles for theme %s", len(articles), theme)

    if not articles:
        return {}

    client, model = get_light_client()
    categorized = defaultdict(list)

    for batch_start in range(0, len(articles), 40):
        batch_articles = articles[batch_start : batch_start + 40]
        batch_result = _categorize_finance_batch(batch_articles, client, model, logger)
        for cat, cat_articles in batch_result.items():
            categorized[cat].extend(cat_articles)

    return {k: v for k, v in categorized.items() if v}


def write_theme_summary(subcategory: str, articles: list[dict]) -> str:
    logger = logging.getLogger(__name__)
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

    logger.info("Writing summary for %s (%s articles)", subcategory, len(articles))
    prompt = render_prompt("write_theme_summary", subcategory=subcategory, context=context)
    result = call_with_retry(
        client,
        model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=32768,
        fallback_models=fallback_models,
    )
    return result or ""


def generate_theme_highlights(summary_text: str, theme: str) -> str:
    client, model, fallback_models = get_heavy_client()
    prompt = render_prompt("generate_theme_highlights", theme=theme, summary_text=summary_text)
    result = call_with_retry(
        client,
        model,
        messages=[{"role": "user", "content": prompt}],
        fallback_models=fallback_models,
    )
    return result or ""


def main():
    runtime_paths = get_runtime_paths()
    ensure_runtime_directories(runtime_paths)

    parser = argparse.ArgumentParser(description="Generate themed digest report")
    parser.add_argument("--theme", required=True, help="Theme name")
    parser.add_argument("--theme-desc", required=True, help="Theme description for filtering")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--md-dir", default=str(runtime_paths.md_dir), help="Directory containing markdown articles")
    parser.add_argument("--output-dir", default=str(runtime_paths.report_dir), help="Directory for generated reports")
    parser.add_argument("--anchor-time", default="08:50", help="Anchor time in HH:MM")
    parser.add_argument("--hours", type=int, default=36, help="Filter articles from past N hours")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--log", help="Log file path")
    parser.add_argument("--test-limit", type=int, default=0, help="Limit number of articles for testing")
    args = parser.parse_args()

    if args.date:
        report_date = args.date
        anchor_hour, anchor_minute = map(int, args.anchor_time.split(":"))
        reference_now = datetime.strptime(args.date, "%Y-%m-%d").replace(
            hour=anchor_hour, minute=anchor_minute, second=0, microsecond=0
        )
    else:
        report_date = datetime.now().strftime("%Y-%m-%d")
        reference_now = datetime.now()

    year, month, _ = report_date.split("-")
    default_dir = os.path.join(args.output_dir, year, month)
    os.makedirs(default_dir, exist_ok=True)

    if not args.output:
        args.output = os.path.join(default_dir, f"{report_date}-{args.theme}.md")
    if not args.log:
        args.log = str(runtime_paths.log_dir / f"digest-{args.theme}-{report_date}.log")

    logger = setup_logging(args.log)
    logger.info("Generating %s digest for %s", args.theme, report_date)
    logger.info("Reference time: %s", reference_now.isoformat())

    date_dirs = get_date_directories(args.md_dir, hours=args.hours, reference_now=reference_now)
    all_files = []
    for date_dir in date_dirs:
        all_files.extend(glob.glob(os.path.join(date_dir, "*.md")))

    cutoff_time = reference_now - timedelta(hours=args.hours)
    md_parser = MarkdownParser()
    articles = []
    for file_path in all_files:
        try:
            article = md_parser.parse(file_path)
            if not article.get("content"):
                continue
            article_date = parse_article_date(article.get("date", ""))
            if article_date and article_date >= cutoff_time:
                articles.append(article)
            elif not article_date and any(date_dir in file_path for date_dir in date_dirs):
                articles.append(article)
        except Exception as e:
            logger.warning("Parse error for %s: %s", file_path, e)

    if args.test_limit > 0:
        articles = articles[: args.test_limit]

    if not articles:
        logger.warning("No articles found in the specified time range")
        sys.exit(1)

    theme_articles = filter_theme_articles(articles, args.theme, args.theme_desc)
    if not theme_articles:
        logger.warning("No articles found for theme: %s", args.theme)
        sys.exit(1)

    categorized = dynamic_subcategorize(theme_articles, args.theme)
    if not categorized:
        logger.warning("Failed to categorize articles")
        sys.exit(1)

    summaries_text = ""
    report_body = ""
    sorted_cats = sorted(categorized.keys(), key=lambda x: len(categorized[x]), reverse=True)
    for subcat in sorted_cats:
        summary = write_theme_summary(subcat, categorized[subcat])
        if summary:
            report_body += f"### {subcat}\n\n{summary}\n\n"
            summaries_text += f"【{subcat}】\n{summary}\n\n"

    highlights = generate_theme_highlights(summaries_text, args.theme)
    report_content = (
        f"# {args.theme}日报\n\n日期: {report_date}\n\n---\n\n"
        f"# {args.theme}情报汇总\n\n## 核心动态\n\n{highlights}\n\n---\n\n"
        f"## 详细内容\n\n{report_body}"
    )

    report_content += "---\n\n## 参考来源\n\n"
    used_articles = set()
    for cat, cat_articles in categorized.items():
        if cat == "其他":
            continue
        for article in cat_articles:
            article_id = article.get("link") or article.get("title", "")
            if article_id in used_articles:
                continue
            used_articles.add(article_id)
            title = article.get("title", "")
            link = article.get("link", "")
            source = article.get("source", "Unknown")
            if link:
                report_content += f"- [{title}]({link}) ({source})\n"
            else:
                report_content += f"- {title} ({source})\n"

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info("DONE! %s report saved to %s", args.theme, args.output)


if __name__ == "__main__":
    main()

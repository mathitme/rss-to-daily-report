#!/usr/bin/env python3
import argparse
import glob
import logging
import os
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from digest.llm_client import (  # noqa: E402
    categorize_articles,
    filter_important_articles,
    generate_three_points,
    write_deep_summary,
)
from digest.parser import MarkdownParser  # noqa: E402
from digest.runtime import ensure_runtime_directories, get_runtime_paths  # noqa: E402


def setup_logging(log_file: str):
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


def main():
    runtime_paths = get_runtime_paths()
    ensure_runtime_directories(runtime_paths)

    parser = argparse.ArgumentParser(description="Generate the main daily digest")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument(
        "--md-dir",
        default=str(runtime_paths.md_dir),
        help="Directory containing markdown articles",
    )
    parser.add_argument(
        "--output-dir",
        default=str(runtime_paths.report_dir),
        help="Directory for generated reports",
    )
    parser.add_argument(
        "--anchor-time",
        default="08:30",
        help="Anchor time for the report in HH:MM format",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=36,
        help="Filter articles from past N hours",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: output-dir/YYYY/MM/YYYY-MM-DD.md)",
    )
    parser.add_argument(
        "--log",
        help="Log file path (default: data/log/digest-YYYY-MM-DD.log)",
    )
    parser.add_argument(
        "--test-limit",
        type=int,
        default=0,
        help="Limit number of articles for testing",
    )
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
        args.output = os.path.join(default_dir, f"{report_date}.md")
    if not args.log:
        args.log = str(runtime_paths.log_dir / f"digest-{report_date}.log")

    logger = setup_logging(args.log)
    logger.info(
        "Generating digest for %s, filtering past %s hours...",
        report_date,
        args.hours,
    )
    logger.info("Reference time: %s", reference_now.isoformat())

    date_dirs = get_date_directories(args.md_dir, hours=args.hours, reference_now=reference_now)
    logger.info("Scanning directories: %s", date_dirs)

    all_files = []
    for date_dir in date_dirs:
        all_files.extend(glob.glob(os.path.join(date_dir, "*.md")))

    logger.info("Found %s total files in date directories", len(all_files))

    cutoff_time = reference_now - timedelta(hours=args.hours)
    logger.info("Cutoff time: %s", cutoff_time.isoformat())
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

    logger.info("Filtered to %s articles from past %s hours", len(articles), args.hours)

    if args.test_limit > 0:
        articles = articles[: args.test_limit]
        logger.info("TEST MODE: Processing first %s articles", len(articles))

    if not articles:
        logger.warning("No articles found in the specified time range")
        return

    important_articles = filter_important_articles(articles)
    categorized = categorize_articles(important_articles)

    logger.info("Writing deep summaries...")
    cat_order = [
        "科技前沿",
        "商业产业",
        "经济股市",
        "政策政治",
        "社会民生",
        "国际新闻",
        "文化娱乐",
    ]

    summaries_text = ""
    report_body = ""
    for cat in cat_order:
        if cat in categorized:
            summary = write_deep_summary(cat, categorized[cat])
            if summary:
                section = f"### {cat}\n\n{summary}\n\n"
                report_body += section
                summaries_text += f"【{cat}】\n{summary}\n\n"

    logger.info("Generating 3 key points...")
    three_points = generate_three_points(summaries_text)

    report_content = (
        f"# 每日资讯摘要\n\n日期: {report_date}\n\n---\n\n"
        f"# 每日情报汇总\n\n## 如果只能记住 3 句话\n\n{three_points}\n\n---\n\n"
        f"## 详细内容\n\n{report_body}"
    )

    report_content += "---\n\n## 参考来源\n\n"
    used_articles = set()
    for _, cat_articles in categorized.items():
        for article in cat_articles:
            article_id = article.get("link") or article.get("title", "")
            if article_id and article_id not in used_articles:
                used_articles.add(article_id)
                title = article.get("title", "")
                link = article.get("link", "")
                source = article.get("source", "") or "未知来源"
                if link:
                    report_content += f"- [{title}]({link}) ({source})\n"
                else:
                    report_content += f"- {title} ({source})\n"

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info("DONE! Report saved to %s", args.output)


if __name__ == "__main__":
    main()

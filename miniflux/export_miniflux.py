#!/usr/bin/env python3
"""Export Miniflux entries to markdown files."""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from miniflux.miniflux_client import MinifluxClient  # noqa: E402
from miniflux.rust_html2md import RustHtml2Markdown  # noqa: E402
from miniflux.storage import StorageManager  # noqa: E402
from digest.runtime import ensure_runtime_directories, get_runtime_paths  # noqa: E402


def log_marked_read_failure(log_path: Path, entry: dict, reason: str):
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry_id = entry.get("id", "")
    title = (entry.get("title") or "").replace("\n", " ").strip()
    url = (entry.get("url") or "").replace("\n", " ").strip()
    feed_title = (entry.get("feed", {}) or {}).get("title", "")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] reason={reason} entry_id={entry_id} feed={feed_title} title={title} url={url}\n"
        )


def export_miniflux(
    base_url: str,
    api_key: str,
    output_dir: str,
    failure_log_path: Path,
    status: str = "unread",
    limit: int = 100,
    mark_as_read: bool = False,
    feed_id: Optional[int] = None,
    force_overwrite: bool = False,
):
    print("Starting Miniflux export...")
    print(f"Server: {base_url}")
    print(f"Output directory: {output_dir}")
    print(f"Entry status: {status}")
    if feed_id:
        print(f"Feed ID: {feed_id}")
    if force_overwrite:
        print("Force overwrite enabled")
    print()

    client = MinifluxClient(base_url, api_key)
    converter = RustHtml2Markdown()
    storage = StorageManager(Path(output_dir))
    failure_log_path.parent.mkdir(parents=True, exist_ok=True)

    if status == "starred":
        result = client.get_starred_entries(limit=limit, fetch_all=True)
        entries = result.get("entries", result) if isinstance(result, dict) else result
    elif status == "all":
        unread_result = client.get_entries(status="unread", fetch_all=True, feed_id=feed_id)
        read_result = client.get_entries(status="read", fetch_all=True, feed_id=feed_id)
        unread_list = unread_result.get("entries", unread_result) if isinstance(unread_result, dict) else unread_result
        read_list = read_result.get("entries", read_result) if isinstance(read_result, dict) else read_result
        entries = unread_list + read_list
        entries.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    else:
        result = client.get_entries(status=status, limit=limit, fetch_all=True, feed_id=feed_id)
        entries = result.get("entries", result) if isinstance(result, dict) else result

    if not entries:
        print("No entries found")
        return

    print(f"Found {len(entries)} entries")
    print()

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, entry in enumerate(entries, 1):
        try:
            title = entry.get("title", "Untitled").strip()
            link = entry.get("url", "")
            content = entry.get("content", "")
            author = entry.get("author", "")
            feed_title = entry.get("feed", {}).get("title", "Unknown")
            published_at = entry.get("published_at")
            date = datetime.fromisoformat(published_at.replace("Z", "+00:00")) if published_at else datetime.now()

            print(f"[{i}/{len(entries)}] Processing: {title}")

            if not content:
                print("  Skip: empty content")
                skip_count += 1
                if mark_as_read and entry.get("id"):
                    client.mark_entry_as_read(entry["id"])
                    log_marked_read_failure(failure_log_path, entry, "empty_content")
                continue

            markdown_content = converter.convert(
                html_content=content,
                preprocess=True,
                preset="standard",
                heading_style="atx",
                code_block_style="backticks",
            )
            if not markdown_content:
                print("  Convert failed")
                fail_count += 1
                if mark_as_read and entry.get("id"):
                    client.mark_entry_as_read(entry["id"])
                    log_marked_read_failure(failure_log_path, entry, "conversion_failed")
                continue

            result_path = storage.save_article(
                title=title,
                content=markdown_content,
                date=date,
                link=link,
                source=feed_title,
                author=author or None,
                check_duplicate=not force_overwrite,
                force_overwrite=force_overwrite,
            )

            if result_path:
                print(f"  Saved: {result_path}")
                success_count += 1
                if mark_as_read and entry.get("id"):
                    client.mark_entry_as_read(entry["id"])
            else:
                print("  Skip: entry already exists")
                skip_count += 1
                if entry.get("id"):
                    client.mark_entry_as_read(entry["id"])
        except Exception as e:
            print(f"  Failed: {e}")
            fail_count += 1
            if mark_as_read and entry.get("id"):
                client.mark_entry_as_read(entry["id"])
                log_marked_read_failure(failure_log_path, entry, "processing_exception")

        print()

    print("=" * 50)
    print("Export completed")
    print(f"Success: {success_count}")
    print(f"Skipped: {skip_count}")
    print(f"Failed: {fail_count}")
    print(f"Total: {len(entries)}")
    print("=" * 50)


def main():
    runtime_paths = get_runtime_paths()
    ensure_runtime_directories(runtime_paths)

    parser = argparse.ArgumentParser(
        description="Export Miniflux entries to markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="Miniflux server URL")
    parser.add_argument("--api-key", required=True, help="Miniflux API key")
    parser.add_argument(
        "--output",
        default=str(runtime_paths.md_dir),
        help="Output directory for exported markdown files",
    )
    parser.add_argument(
        "--status",
        choices=["unread", "read", "all", "starred"],
        default="unread",
        help="Entry status",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum entries per run")
    parser.add_argument("--mark-read", action="store_true", help="Mark exported entries as read")
    parser.add_argument("--feed-id", type=int, help="Optional feed ID filter")
    parser.add_argument("--refresh-feed", type=int, help="Refresh and export a specific feed")
    parser.add_argument("--list-feeds", action="store_true", help="List all feeds")
    parser.add_argument("--force-overwrite", action="store_true", help="Overwrite existing markdown files")
    args = parser.parse_args()

    client = MinifluxClient(args.url, args.api_key)
    if args.list_feeds:
        feeds = client.get_feeds()
        if not feeds:
            print("No feeds found")
            return
        print(f"Found {len(feeds)} feeds:\n")
        for feed in feeds:
            print(f"ID: {feed.get('id')}")
            print(f"  Title: {feed.get('title')}")
            print(f"  URL: {feed.get('feed_url')}")
            print(f"  Entries: {feed.get('total_entries', 0)}")
            print()
        return

    if args.refresh_feed:
        print(f"Refreshing feed ID: {args.refresh_feed}...")
        if client.refresh_feed(args.refresh_feed):
            print("Feed refresh succeeded")
            print("Waiting 5 seconds before export...")
            time.sleep(5)
            export_miniflux(
                base_url=args.url,
                api_key=args.api_key,
                output_dir=args.output,
                failure_log_path=runtime_paths.log_dir / "miniflux-read-failures.log",
                status="unread",
                limit=args.limit,
                mark_as_read=args.mark_read,
                feed_id=args.refresh_feed,
                force_overwrite=args.force_overwrite,
            )
        else:
            print("Feed refresh failed")
        return

    export_miniflux(
        base_url=args.url,
        api_key=args.api_key,
        output_dir=args.output,
        failure_log_path=runtime_paths.log_dir / "miniflux-read-failures.log",
        status=args.status,
        limit=args.limit,
        mark_as_read=args.mark_read,
        feed_id=args.feed_id,
        force_overwrite=args.force_overwrite,
    )


if __name__ == "__main__":
    main()

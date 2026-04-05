#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from digest.emailer import EmailSendError, send_report_email  # noqa: E402
from digest.runtime import ensure_runtime_directories, get_runtime_settings  # noqa: E402


def send_if_enabled(subject: str, report_path: str) -> None:
    settings = get_runtime_settings()
    ensure_runtime_directories(settings.paths)
    if not settings.email.enabled:
        return
    try:
        send_report_email(subject, report_path, settings.email)
        print(f"Email sent: {report_path}")
    except EmailSendError as e:
        print(f"Email send skipped: {e}")
    except Exception as e:
        print(f"Email send failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Send a generated report by SMTP if email is configured")
    parser.add_argument("--report", required=True, help="Report file path")
    parser.add_argument("--subject", required=True, help="Email subject")
    args = parser.parse_args()
    send_if_enabled(args.subject, args.report)


if __name__ == "__main__":
    main()

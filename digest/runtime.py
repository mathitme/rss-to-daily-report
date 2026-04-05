import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_MD_DIR = DEFAULT_DATA_DIR / "md"
DEFAULT_REPORT_DIR = DEFAULT_DATA_DIR / "report"
DEFAULT_PROMPT_DIR = DEFAULT_DATA_DIR / "prompt"
DEFAULT_LOG_DIR = DEFAULT_DATA_DIR / "log"


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    data_dir: Path
    md_dir: Path
    report_dir: Path
    prompt_dir: Path
    log_dir: Path


@dataclass(frozen=True)
class EmailSettings:
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    from_address: str
    to_address: str


@dataclass(frozen=True)
class RuntimeSettings:
    paths: RuntimePaths
    email: EmailSettings


def _resolve_path(env_name: str, default_path: Path) -> Path:
    value = os.environ.get(env_name)
    if value:
        return Path(value).expanduser().resolve()
    return default_path.resolve()


def get_runtime_paths() -> RuntimePaths:
    project_root = _resolve_path("DAILYREPORT_PROJECT_DIR", PROJECT_ROOT)
    data_dir = _resolve_path("DAILYREPORT_DATA_DIR", project_root / "data")
    md_dir = _resolve_path("DAILYREPORT_MD_DIR", data_dir / "md")
    report_dir = _resolve_path("DAILYREPORT_REPORT_DIR", data_dir / "report")
    prompt_dir = _resolve_path("DAILYREPORT_PROMPT_DIR", data_dir / "prompt")
    log_dir = _resolve_path("DAILYREPORT_LOG_DIR", data_dir / "log")

    return RuntimePaths(
        project_root=project_root,
        data_dir=data_dir,
        md_dir=md_dir,
        report_dir=report_dir,
        prompt_dir=prompt_dir,
        log_dir=log_dir,
    )


def get_email_settings() -> EmailSettings:
    smtp_host = os.environ.get("DAILYREPORT_SMTP_HOST", "")
    smtp_port = int(os.environ.get("DAILYREPORT_SMTP_PORT", "587"))
    smtp_user = os.environ.get("DAILYREPORT_SMTP_USER", "")
    smtp_password = os.environ.get("DAILYREPORT_SMTP_PASSWORD", "")
    from_address = os.environ.get("DAILYREPORT_SMTP_FROM", "")
    to_address = os.environ.get("DAILYREPORT_MAIL_RECIPIENT", "")
    smtp_use_tls = os.environ.get("DAILYREPORT_SMTP_USE_TLS", "true").lower() == "true"
    smtp_use_ssl = os.environ.get("DAILYREPORT_SMTP_USE_SSL", "false").lower() == "true"
    enabled = bool(smtp_host and from_address and to_address)

    return EmailSettings(
        enabled=enabled,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_use_tls=smtp_use_tls,
        smtp_use_ssl=smtp_use_ssl,
        from_address=from_address,
        to_address=to_address,
    )


def get_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(paths=get_runtime_paths(), email=get_email_settings())


def ensure_runtime_directories(paths: RuntimePaths) -> None:
    for directory in (
        paths.data_dir,
        paths.md_dir,
        paths.report_dir,
        paths.prompt_dir,
        paths.log_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

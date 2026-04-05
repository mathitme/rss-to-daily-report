import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config_data = {}
        self._load()

    def _load_yaml_file(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError:
                return {}

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load(self):
        base_config = self._load_yaml_file(self.config_path)

        if self.config_path.name == "config.yaml":
            local_override_path = self.config_path.with_name("config.local.yaml")
            local_config = self._load_yaml_file(local_override_path)
            self.config_data = self._deep_merge(base_config, local_config)
        else:
            self.config_data = base_config

    def get(self, key: str, default: Any = None) -> Any:
        return self.config_data.get(key, default)

    def get_api_key(self, provider: str) -> str:
        env_var = f"{provider.upper()}_API_KEY"
        return os.environ.get(env_var, "")


class MarkdownParser:
    def __init__(self):
        self.yaml_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
        self.content_pattern = re.compile(r'^---\s*\n.*?\n---\s*\n(.*)', re.DOTALL)
        self.title_re = re.compile(r"^#\s+(.+)$", re.MULTILINE)
        self.source_re = re.compile(r"^\*\*来源\*\*:\s*(.+)", re.MULTILINE)
        self.date_re = re.compile(r"^\*\*发布时间\*\*:\s*(.+)", re.MULTILINE)
        self.md_link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    def parse(self, file_path: str) -> dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        frontmatter = {}
        yaml_match = self.yaml_pattern.match(raw_content)
        if yaml_match:
            try:
                frontmatter = yaml.safe_load(yaml_match.group(1)) or {}
            except Exception:
                pass

        title = frontmatter.get('title', '')
        if not title:
            title_match = self.title_re.search(raw_content)
            title = title_match.group(1).strip() if title_match else os.path.basename(file_path)

        source = frontmatter.get('source', '')
        if not source:
            source_match = self.source_re.search(raw_content)
            source = source_match.group(1).strip() if source_match else 'Unknown'

        date = frontmatter.get('date', '')
        if not date:
            date_match = self.date_re.search(raw_content)
            date = date_match.group(1).strip() if date_match else 'Unknown'

        link = frontmatter.get('link', '')
        if not link:
            link_match = self.md_link_pattern.search(raw_content)
            if link_match:
                link = link_match.group(2)

        content_match = self.content_pattern.search(raw_content)
        if content_match:
            body = content_match.group(1).strip()
        else:
            body = raw_content
            body = re.sub(r'^#\s+.+\n', '', body, count=1).strip()

        return {
            "title": title,
            "content": body,
            "id": os.path.basename(file_path),
            "source": source,
            "date": date,
            "link": link,
        }

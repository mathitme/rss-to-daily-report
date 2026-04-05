from pathlib import Path

from digest.runtime import get_runtime_paths


def load_prompt_template(name: str) -> str:
    prompt_path = get_runtime_paths().prompt_dir / f"{name}.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def render_prompt(name: str, **kwargs) -> str:
    template = load_prompt_template(name)
    return template.format(**kwargs)

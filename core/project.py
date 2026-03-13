"""Project persistence."""

from __future__ import annotations

import json
import shutil
from datetime import datetime

from core.config import PROJECTS_DIR


class ProjectManager:
    """Create, load, and delete simple workspace projects."""

    def __init__(self) -> None:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[dict]:
        projects: list[dict] = []
        for directory in PROJECTS_DIR.iterdir():
            if not directory.is_dir():
                continue
            project_file = directory / "project.json"
            if not project_file.exists():
                continue
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
                data["name"] = directory.name
                projects.append(data)
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(projects, key=lambda item: item.get("created_at", ""), reverse=True)

    def create_project(self, name: str, description: str = "") -> dict:
        project_dir = PROJECTS_DIR / name
        project_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "prompts": [],
            "settings": {},
            "batch_config": {},
        }
        (project_dir / "project.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return data

    def load_project(self, name: str) -> dict | None:
        project_file = PROJECTS_DIR / name / "project.json"
        if not project_file.exists():
            return None
        return json.loads(project_file.read_text(encoding="utf-8"))

    def save_project(self, name: str, data: dict) -> None:
        project_dir = PROJECTS_DIR / name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "project.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete_project(self, name: str) -> bool:
        project_dir = PROJECTS_DIR / name
        if not project_dir.exists():
            return False
        shutil.rmtree(project_dir)
        return True

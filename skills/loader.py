# -*- coding: utf-8 -*-
"""Skill file loader - scans directories for Markdown skill files.

Implements R20-R21 from the plan.
Supports hot-reload via watchdog.
"""
import os
import warnings
from pathlib import Path
from typing import Callable

from ..utils.frontmatter import load_frontmatter_file, FrontmatterDoc
from .registry import Skill, SkillRegistry


# Priority levels
PRIORITY_BUNDLED = 0
PRIORITY_USER = 10
PRIORITY_PROJECT = 20


class SkillLoader:
    """Loads skill files from multiple directories."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._watcher = None

    def load_bundled(self) -> int:
        """Load bundled skills from the package."""
        bundled_dir = Path(__file__).parent / "bundled"
        return self._load_directory(bundled_dir, priority=PRIORITY_BUNDLED)

    def load_user_skills(self) -> int:
        """Load user skills from ~/.config/codeagent/skills/."""
        user_dir = Path.home() / ".config" / "codeagent" / "skills"
        return self._load_directory(user_dir, priority=PRIORITY_USER)

    def load_project_skills(self, project_root: str | None = None) -> int:
        """Load project skills from .agent/skills/."""
        root = Path(project_root) if project_root else Path.cwd()
        project_dir = root / ".agent" / "skills"
        return self._load_directory(project_dir, priority=PRIORITY_PROJECT)

    def load_all(self, project_root: str | None = None) -> int:
        """Load all skills: bundled + user + project."""
        total = 0
        total += self.load_bundled()
        total += self.load_user_skills()
        total += self.load_project_skills(project_root)
        return total

    def _load_directory(self, directory: Path, priority: int) -> int:
        """Load all .md skill files from a directory.

        Returns:
            Number of skills loaded.
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        count = 0
        for fpath in directory.glob("*.md"):
            try:
                skill = self._parse_skill_file(fpath, priority)
                if skill:
                    self._registry.register(skill)
                    count += 1
            except Exception as e:
                warnings.warn(
                    f"Failed to load skill from {fpath}: {e}",
                    stacklevel=2,
                )

        return count

    def _parse_skill_file(self, path: Path, priority: int) -> Skill | None:
        """Parse a single skill Markdown file with frontmatter."""
        doc = load_frontmatter_file(str(path))
        meta = doc.metadata

        name = meta.get("name", path.stem)
        if not name:
            return None

        return Skill(
            name=name,
            description=meta.get("description", ""),
            when_to_use=meta.get("whenToUse", meta.get("when_to_use", "")),
            allowed_tools=meta.get("allowedTools", meta.get("allowed_tools", [])),
            model=meta.get("model"),
            prompt=doc.body,
            source_path=str(path),
            priority=priority,
        )

    def start_watching(self, directories: list[str] | None = None) -> None:
        """Start file watcher for skill hot-reload."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class SkillReloadHandler(FileSystemEventHandler):
                def __init__(self, loader: 'SkillLoader'):
                    self.loader = loader

                def on_modified(self, event):
                    if event.src_path.endswith(".md"):
                        self.loader.load_all()

                def on_created(self, event):
                    if event.src_path.endswith(".md"):
                        self.loader.load_all()

            observer = Observer()
            handler = SkillReloadHandler(self)

            watch_dirs = directories or []
            # Default directories
            watch_dirs.extend([
                str(Path(__file__).parent / "bundled"),
                str(Path.home() / ".config" / "codeagent" / "skills"),
                str(Path.cwd() / ".agent" / "skills"),
            ])

            for d in watch_dirs:
                if os.path.isdir(d):
                    observer.schedule(handler, d, recursive=False)

            observer.start()
            self._watcher = observer

        except ImportError:
            pass  # watchdog not installed, skip hot-reload

    def stop_watching(self) -> None:
        """Stop the file watcher."""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join()
            self._watcher = None

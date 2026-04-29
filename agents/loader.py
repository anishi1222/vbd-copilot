"""Agent loading - parse agent definitions from the filesystem.

The primary source is ``*.agent.md`` files with YAML frontmatter in a
directory. The ``AgentSource`` protocol allows plugging in alternative
backends (database, HTTP, etc.) in the future.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

from agents.models import AgentConfig


@runtime_checkable
class AgentSource(Protocol):
    """Protocol for anything that can supply agent definitions."""

    def load_all(self) -> list[AgentConfig]:
        """Return every available agent definition."""
        ...


class FileSystemAgentSource:
    """Load agents from ``*.agent.md`` files in a directory.

    File format::

        ---
        name: agent-id
        display_name: Human Label
        description: Short description for the router
        infer: true
        model: claude-sonnet-4.6
        timeout: 900
        tools: [str_replace_editor, task]
        skills: [pptx-generator]
        ---
        Markdown system prompt / instructions

    Results are cached in-memory.  Staleness is detected with ``stat()``
    calls only — no file I/O on the hot path.  Two signals trigger a reload:

    * A directory ``mtime`` changed → a file was added or removed inside it.
    * A file ``mtime`` changed → the file was modified in-place.

    When a reload is required, only files whose ``mtime`` actually changed
    are re-parsed; all other configs are returned straight from the cache.
    """

    def __init__(self, defs_dir: Path) -> None:
        self._defs_dir = defs_dir
        # {file_path: (mtime, AgentConfig)} — per-file result cache
        self._file_cache: dict[Path, tuple[float, AgentConfig]] = {}
        # {dir_path: mtime} — tracks directory shape to detect add/remove
        self._dir_mtimes: dict[Path, float] = {}
        # Last full result list; None means "not yet loaded"
        self._cached_result: list[AgentConfig] | None = None

    # -- Staleness detection -----------------------------------------------

    def _snapshot_dir_mtimes(self) -> dict[Path, float]:
        """stat() every directory under defs_dir and return {path: mtime}."""
        mtimes: dict[Path, float] = {}
        try:
            mtimes[self._defs_dir] = self._defs_dir.stat().st_mtime
        except OSError:
            return mtimes
        for p in self._defs_dir.rglob("*"):
            if p.is_dir():
                try:
                    mtimes[p] = p.stat().st_mtime
                except OSError:
                    pass
        return mtimes

    def is_stale(self) -> bool:
        """Return True if any tracked file or directory changed on disk.

        Uses only ``stat()`` syscalls — no file content reads — so this is
        very fast even with hundreds of agent files.

        * Known *directory* mtimes catch files being added or removed (the
          parent directory's mtime changes whenever its children change).
        * Known *file* mtimes catch in-place modifications.
        """
        for d, cached_mtime in self._dir_mtimes.items():
            try:
                if d.stat().st_mtime != cached_mtime:
                    return True
            except OSError:
                return True  # directory was removed
        for f, (cached_mtime, _) in self._file_cache.items():
            try:
                if f.stat().st_mtime != cached_mtime:
                    return True
            except OSError:
                return True  # file was removed
        return False

    # -- Public API --------------------------------------------------------

    def load_all(self) -> list[AgentConfig]:
        """Return agent configs, reloading from disk only when something changed.

        Hot path (nothing changed): a handful of ``stat()`` syscalls, zero
        file reads.  Cold path (something changed): only *modified* files are
        re-parsed; all unchanged configs come from the in-memory cache.
        """
        if self._cached_result is not None and not self.is_stale():
            return list(self._cached_result)

        # --- Refresh path ---
        new_dir_mtimes = self._snapshot_dir_mtimes()
        agents: list[AgentConfig] = []
        seen: set[Path] = set()

        for md_file in sorted(self._defs_dir.rglob("*.agent.md")):
            seen.add(md_file)
            try:
                mtime = md_file.stat().st_mtime
            except OSError:
                continue  # disappeared between rglob and stat
            cached = self._file_cache.get(md_file)
            if cached is not None and cached[0] == mtime:
                agents.append(cached[1])
            else:
                config = load_agent(md_file)
                self._file_cache[md_file] = (mtime, config)
                agents.append(config)

        # Evict entries for files that no longer exist
        for path in set(self._file_cache) - seen:
            del self._file_cache[path]

        self._dir_mtimes = new_dir_mtimes
        self._cached_result = agents
        return list(agents)


def load_agent(path: Path) -> AgentConfig:
    """Parse a single ``*.agent.md`` agent definition file."""
    text = path.read_text()
    try:
        _, fm_block, prompt = text.split("---", 2)
    except ValueError:
        raise ValueError(
            f"Agent definition {path} is missing YAML frontmatter delimiters (---)"
        )
    raw = yaml.safe_load(fm_block)
    if not isinstance(raw, dict):
        raise ValueError(f"Agent definition {path} has invalid YAML frontmatter")
    prompt = prompt.strip()

    return AgentConfig(
        name=raw["name"],
        display_name=raw["display_name"],
        description=raw["description"],
        prompt=prompt,
        tools=raw.get("tools", []),
        infer=raw.get("infer", False),
    )

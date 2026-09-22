from __future__ import annotations

from pathlib import Path

from llm_operations_lab.errors import PromptNotFoundError


class PromptStore:
    def __init__(self, root: Path | str = "prompts") -> None:
        self._root = Path(root).resolve()

    def system_prompt(self, version: str) -> str:
        candidate = (self._root / version / "system.txt").resolve()
        if self._root not in candidate.parents:
            raise PromptNotFoundError("versão de prompt inválida")
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise PromptNotFoundError(f"prompt {version} não encontrado") from exc


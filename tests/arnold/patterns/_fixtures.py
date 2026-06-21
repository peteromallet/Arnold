"""Stable importable hooks for pattern purity tests."""

from __future__ import annotations


def agent_prompt(draft: str) -> str:
    return f"prompt({draft})"


def decide_condition(values: dict[str, str]) -> bool:
    return True


def reducer(values: tuple[str, ...]) -> str:
    return ",".join(values)


def judge_winner(candidates: tuple[str, ...]) -> str | None:
    return candidates[0] if candidates else None


class HookFixtures:
    @staticmethod
    def static_prompt(draft: str) -> str:
        return f"static({draft})"

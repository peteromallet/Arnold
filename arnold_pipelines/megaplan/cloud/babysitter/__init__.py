"""Single-flash status-trigger babysitter: ONE detached Flash managed agent.

The watchdog's status trigger (``MEGAPLAN_SUPERFIXER_ONLY=1``) launches the
``arnold-babysitter`` wrapper, which runs this package's ``launch`` module.
The launch module spawns ONE managed ``omp:deepseek/deepseek-v4-flash``
agent whose goal prompt drives the whole swarm -> codex -> implement ->
relaunch -> prove recovery flow.  There is no coded multi-stage orchestrator
anymore: the single agent IS the orchestrator.

``launch_babysitter`` is exported lazily so ``python -m
arnold_pipelines.megaplan.cloud.babysitter.launch`` never double-imports the
module through this package (runpy would find it already in ``sys.modules``).
"""

__all__ = ["launch_babysitter"]


def __getattr__(name: str):
    if name == "launch_babysitter":
        from arnold_pipelines.megaplan.cloud.babysitter.launch import (
            launch_babysitter,
        )

        return launch_babysitter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

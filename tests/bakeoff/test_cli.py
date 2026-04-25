import argparse

from megaplan.bakeoff.cli import build_bakeoff_parser


def test_bakeoff_run_robustness_parsing() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    build_bakeoff_parser(subparsers)

    args = parser.parse_args(["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p", "--robustness", "light"])
    assert args.robustness == "light"

    args = parser.parse_args(["bakeoff", "run", "--idea-file", "i.md", "--profiles", "p"])
    assert args.robustness is None

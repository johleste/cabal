#!/usr/bin/env python3
"""
Cabal — local multi-agent AI system.
deepseek-r1 commands a council of specialist Ollama models.

Usage:
  cabal run "task"              Commander orchestrates agents to complete a task
  cabal ask "question"          Commander answers directly (no agent dispatch)
  cabal research "topic"        Direct to Researcher
  cabal code "task"             Direct to Coder
  cabal recon "scenario"        Direct to Recon
  cabal analyse "task"          Direct to Analyst
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.commander import Commander
from agents.researcher import ResearcherAgent
from agents.coder import CoderAgent
from agents.recon import ReconAgent
from agents.analyst import AnalystAgent

_AGENTS = {
    "RESEARCHER": ResearcherAgent(),
    "CODER":      CoderAgent(),
    "RECON":      ReconAgent(),
    "ANALYST":    AnalystAgent(),
}
_COMMANDER = Commander()


def cmd_run(args):
    task = " ".join(args.task)
    result = _COMMANDER.run(task, _AGENTS)
    print(result["result"])


def cmd_ask(args):
    question = " ".join(args.question)
    print(_COMMANDER.ask(question))


def cmd_research(args):
    print(ResearcherAgent().run(" ".join(args.task)))


def cmd_code(args):
    print(CoderAgent().run(" ".join(args.task)))


def cmd_recon(args):
    print(ReconAgent().run(" ".join(args.task)))


def cmd_analyse(args):
    print(AnalystAgent().run(" ".join(args.task)))


def main():
    parser = argparse.ArgumentParser(
        prog="cabal",
        description="Cabal — local multi-agent AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Commander orchestrates agents")
    run_p.add_argument("task", nargs="+")
    run_p.set_defaults(func=cmd_run)

    ask_p = sub.add_parser("ask", help="Commander answers directly")
    ask_p.add_argument("question", nargs="+")
    ask_p.set_defaults(func=cmd_ask)

    res_p = sub.add_parser("research", help="Direct to Researcher")
    res_p.add_argument("task", nargs="+")
    res_p.set_defaults(func=cmd_research)

    cod_p = sub.add_parser("code", help="Direct to Coder")
    cod_p.add_argument("task", nargs="+")
    cod_p.set_defaults(func=cmd_code)

    rec_p = sub.add_parser("recon", help="Direct to Recon")
    rec_p.add_argument("task", nargs="+")
    rec_p.set_defaults(func=cmd_recon)

    ana_p = sub.add_parser("analyse", help="Direct to Analyst")
    ana_p.add_argument("task", nargs="+")
    ana_p.set_defaults(func=cmd_analyse)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

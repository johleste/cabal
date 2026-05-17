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
  cabal pull                    Print the latest session file
  cabal pull --path              Print the path to the latest session file
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import session
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
    session.start("run", task)
    result = _COMMANDER.run(task, _AGENTS)
    session.finish(result["result"])
    print(result["result"])


def cmd_ask(args):
    question = " ".join(args.question)
    session.start("ask", question)
    result = _COMMANDER.ask(question)
    session.finish(result)
    print(result)


def cmd_research(args):
    task = " ".join(args.task)
    session.start("research", task)
    result = ResearcherAgent().run(task)
    session.finish(result)
    print(result)


def cmd_code(args):
    task = " ".join(args.task)
    session.start("code", task)
    result = CoderAgent().run(task)
    session.finish(result)
    print(result)


def cmd_recon(args):
    task = " ".join(args.task)
    session.start("recon", task)
    result = ReconAgent().run(task)
    session.finish(result)
    print(result)


def cmd_analyse(args):
    task = " ".join(args.task)
    session.start("analyse", task)
    result = AnalystAgent().run(task)
    session.finish(result)
    print(result)


def cmd_pull(args):
    path = session.latest()
    if not path:
        print("[cabal] no sessions found in ./sessions/")
        return
    if args.path:
        print(path)
    else:
        print(path.read_text())


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

    pull_p = sub.add_parser("pull", help="Print the latest session output")
    pull_p.add_argument("--path", action="store_true", help="Print file path only")
    pull_p.set_defaults(func=cmd_pull)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

"""
Claude Code consultation. Invoked between retry attempts when Commander is
genuinely stuck — same error, no progress across consecutive attempts.

Sends the task and a summary of what failed to `claude --print` and returns
guidance. Commander still does all the work; this only provides direction.

Rate limit handling:
  - No timestamp: exponential backoff (2s → 4s → 8s → 16s → 32s, 5 attempts)
  - Timestamp present: schedule a cron job via `at` (or crontab fallback) to
    re-run the original cabal command 1 minute after the given timestamp, then
    exit the current process.
"""
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agents import llmlog

TIMEOUT = 120        # seconds per claude call
MAX_BACKOFF = 5      # max retry attempts on rate limit without timestamp
_BACKOFF_BASE = 2    # initial backoff seconds, doubles each attempt

_PROMPT = """\
You are being consulted by Cabal, a local autonomous multi-agent AI system.
Cabal has been trying to complete a coding task but is genuinely stuck —
it has made no measurable progress across multiple attempts (same errors,
same exit codes repeating).

TASK:
{task}

PRIOR ATTEMPTS (what was tried and failed):
{prior_notes}

Cabal needs a specific, actionable hint to break out of this loop.
Please provide:
1. What is likely wrong with the approaches tried so far
2. A concrete alternative strategy or key technical insight to try next

Be specific and technical. Short code snippets or pseudocode are welcome if
they illustrate the direction. Do not solve the entire task — Cabal will
implement it. Just give the hint or redirect it needs.
"""

_RATE_LIMIT_KEYWORDS = ("rate limit", "rate_limit", "ratelimit", "quota",
                         "too many requests", "429", "overloaded")


def consult(task: str, prior_notes: str) -> str:
    prompt = _PROMPT.format(task=task, prior_notes=prior_notes)
    llmlog.consult_start()

    delay = _BACKOFF_BASE
    for attempt in range(MAX_BACKOFF):
        try:
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )

            if result.returncode == 0 and result.stdout.strip():
                llmlog.consult_end(success=True)
                return result.stdout.strip()

            err_text = (result.stderr or "") + (result.stdout or "")
            rate_info = _parse_rate_limit(err_text)

            if rate_info is None:
                # Not a rate limit — genuine failure, don't retry
                llmlog.consult_end(success=False)
                return f"[consultation failed: {err_text.strip()[:300]}]"

            ts = rate_info.get("timestamp")
            if ts is not None:
                # Timestamp given — schedule cron and exit
                _schedule_and_exit(ts)

            # Rate limited, no timestamp — backoff and retry
            if attempt < MAX_BACKOFF - 1:
                llmlog.consult_backoff(attempt + 1, delay)
                time.sleep(delay)
                delay = min(delay * 2, 64)
                continue

            llmlog.consult_end(success=False)
            return f"[consultation failed: rate limited after {MAX_BACKOFF} attempts]"

        except subprocess.TimeoutExpired:
            llmlog.consult_end(success=False)
            return f"[consultation timed out after {TIMEOUT}s]"
        except FileNotFoundError:
            llmlog.consult_end(success=False)
            return "[consultation failed: claude CLI not found in PATH]"
        except Exception as e:
            llmlog.consult_end(success=False)
            return f"[consultation failed: {e}]"

    llmlog.consult_end(success=False)
    return "[consultation failed: rate limited, max backoff reached]"


# ── Rate limit detection ──────────────────────────────────────────────────────

def _parse_rate_limit(text: str) -> dict | None:
    """
    Returns None if not a rate limit error.
    Returns {} if rate limited but no retry timestamp found.
    Returns {"timestamp": datetime} if a retry time was parsed.
    """
    lower = text.lower()
    if not any(k in lower for k in _RATE_LIMIT_KEYWORDS):
        return None

    # "retry after N seconds"
    m = re.search(r"retry.{0,10}after\s+(\d+)\s*second", lower)
    if m:
        secs = int(m.group(1))
        return {"timestamp": datetime.now(timezone.utc) + timedelta(seconds=secs)}

    # ISO 8601: 2026-05-18T15:30:00[Z or offset]
    m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?", text)
    if m:
        raw = m.group(0).rstrip("Z")
        try:
            ts = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
            return {"timestamp": ts}
        except ValueError:
            pass

    # Unix epoch (10-digit number)
    m = re.search(r"\b(1[5-9]\d{8}|2\d{9})\b", text)
    if m:
        return {"timestamp": datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)}

    # HH:MM[:SS] bare time — assume today, or tomorrow if already past
    m = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", text)
    if m:
        now = datetime.now(timezone.utc)
        h, mn, sc = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        ts = now.replace(hour=h, minute=mn, second=sc, microsecond=0)
        if ts <= now:
            ts += timedelta(days=1)
        return {"timestamp": ts}

    return {}  # rate limited but no parseable timestamp


# ── Scheduling ────────────────────────────────────────────────────────────────

def _schedule_and_exit(retry_after: datetime):
    """Schedule a one-shot job to re-run this cabal command 1 min after retry_after, then exit."""
    retry_time = retry_after.astimezone(timezone.utc) + timedelta(minutes=1)

    # Reconstruct the original command as: python3 /abs/path/cabal.py <args>
    cabal_py = os.path.abspath(sys.argv[0])
    cmd_parts = [sys.executable, cabal_py] + sys.argv[1:]
    cabal_cmd = " ".join(shlex.quote(p) for p in cmd_parts)

    scheduled = _try_at(retry_time, cabal_cmd) or _try_crontab(retry_time, cabal_cmd)

    if scheduled:
        llmlog.consult_scheduled(retry_time, method=scheduled)
    else:
        llmlog.error("consult", "could not schedule retry (at and crontab both failed)")

    sys.exit(0)


def _try_at(retry_time: datetime, cmd: str) -> str | None:
    """Schedule via `at`. Returns 'at' on success, None on failure."""
    # POSIX -t format: [[CC]YY]MMDDhhmm[.SS]
    at_time = retry_time.strftime("%Y%m%d%H%M")
    try:
        result = subprocess.run(
            ["at", "-t", at_time],
            input=cmd + "\n",
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return "at"
    except FileNotFoundError:
        pass
    return None


def _try_crontab(retry_time: datetime, cmd: str) -> str | None:
    """Schedule via crontab with a self-removing wrapper script. Returns 'crontab' on success."""
    try:
        # Write a temp script that runs the command then removes itself from crontab
        fd, script_path = tempfile.mkstemp(prefix="cabal_retry_", suffix=".sh")
        os.close(fd)
        tag = os.path.basename(script_path)
        script = (
            "#!/bin/bash\n"
            f"{cmd}\n"
            f'crontab -l | grep -v "{tag}" | crontab -\n'
            f'rm -- "$0"\n'
        )
        with open(script_path, "w") as f:
            f.write(script)
        os.chmod(script_path, stat.S_IRWXU)

        cron_time = retry_time.strftime("%-M %-H %-d %-m")
        cron_line = f"{cron_time} * {script_path}"

        existing = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        ).stdout.rstrip()
        new_crontab = (existing + "\n" if existing else "") + cron_line + "\n"
        result = subprocess.run(
            ["crontab", "-"], input=new_crontab, capture_output=True, text=True
        )
        if result.returncode == 0:
            return "crontab"
        os.unlink(script_path)
    except Exception as e:
        llmlog.error("consult", f"crontab scheduling failed: {e}")
    return None

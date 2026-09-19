# AutoBDP - Automated Binary Decompiler Pipeline
# Copyright (C) 2026 Shubham Mahato (oopsiedoopsie)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# Cooperative cancellation for long-running / looping pipeline steps
# (Gemini API retry loops, compilation-repair loops, backoff sleeps).
#
# This module has zero dependencies on tkinter or anything GUI-specific,
# so it's safe to import from LLM_stuff.py / pre_run_checks.py regardless
# of whether they're driven by auto-bdp.py (CLI) or gui.py. When nobody
# ever calls request_stop(), everything here is a no-op.

import time
import threading

_stop_event = threading.Event()


class PipelineCancelled(Exception):
    """Raised to unwind a pipeline step when the user requests a stop."""
    pass


def request_stop():
    """Call from the controlling UI/CLI to ask any running pipeline to halt."""
    _stop_event.set()


def reset():
    """Call before starting a new pipeline run."""
    _stop_event.clear()


def is_stopping():
    return _stop_event.is_set()


def check():
    """
    Call this periodically from inside any loop that could run for a while
    (API retry loops, streaming response loops, compile-repair loops).
    Raises PipelineCancelled the first time it notices a stop request.
    """
    if _stop_event.is_set():
        raise PipelineCancelled()


def sleep_cancellable(seconds, poll_interval=0.5):
    """
    Drop-in replacement for time.sleep() that wakes up early (and raises
    PipelineCancelled) if a stop is requested mid-sleep, instead of blocking
    for the full duration - important for the 30s API backoff sleeps.
    """
    elapsed = 0.0
    while elapsed < seconds:
        check()
        chunk = min(poll_interval, seconds - elapsed)
        time.sleep(chunk)
        elapsed += chunk
    check()

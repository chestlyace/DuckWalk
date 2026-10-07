"""The one place Sentry is initialised. Import `init_sentry()` from every entry point.

Traces carry metadata only (stage timings, model name, token counts).
Never attach code, diffs, prompts or transcripts to events or spans.
"""

import sentry_sdk

from duckwalk import config

_initialised = False


def init_sentry() -> bool:
    """Initialise Sentry once. Returns False when no DSN is configured."""
    global _initialised
    if _initialised:
        return True
    if not config.SENTRY_DSN:
        return False
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=1.0,
        send_default_pii=False,
    )
    _initialised = True
    return True

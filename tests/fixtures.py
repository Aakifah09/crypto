"""Zero-argument test functions the runner can measure with  --targets fn:tests.fixtures:<name>."""
import os
import random
import time


def _burn_ms(ms: float) -> None:
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        pass


def ok_fn():
    return sum(i * i for i in range(2000))


def raises_fn():
    raise RuntimeError("deliberate failure")


def sleeps_fn():
    time.sleep(30)


def slowish_fn():
    time.sleep(0.2)


def synthetic_fn():
    """Busy-wait of 0.5 ms x SYNTH_SLOWDOWN; fails with probability SYNTH_FAIL_RATE.
    Only used to demonstrate the pipeline on synthetic data; it measures nothing real."""
    if random.random() < float(os.environ.get("SYNTH_FAIL_RATE", "0")):
        raise MemoryError("synthetic failure")
    _burn_ms(0.5 * float(os.environ.get("SYNTH_SLOWDOWN", "1")) * random.uniform(0.97, 1.03))

import logging
import time

from openai import OpenAI

log = logging.getLogger(__name__)
client = OpenAI(timeout=30.0, max_retries=3)


def run(attempts=3):
    for attempt in range(attempts):
        try:
            return client.chat.completions.create(model="demo", messages=[], timeout=30)
        except TimeoutError as exc:
            log.warning("provider timeout attempt=%s err=%s", attempt, exc)
            time.sleep(2**attempt)
    raise RuntimeError("provider attempts exhausted")

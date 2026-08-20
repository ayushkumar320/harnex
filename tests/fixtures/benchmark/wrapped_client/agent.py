from openai import OpenAI

from agentharness import wrap

client = wrap(OpenAI())


def run():
    return client.chat.completions.create(model="demo", messages=[])

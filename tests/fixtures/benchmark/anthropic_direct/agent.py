import anthropic


def run():
    client = anthropic.Anthropic()
    return client.messages.create(model="demo", max_tokens=16, messages=[])

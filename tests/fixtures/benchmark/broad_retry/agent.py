from openai import OpenAI


def run():
    client = OpenAI()
    try:
        return client.chat.completions.create(model="demo", messages=[])
    except Exception:
        return client.chat.completions.create(model="demo", messages=[])

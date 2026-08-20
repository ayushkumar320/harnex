from openai import OpenAI

client = OpenAI()


def run():
    while True:
        try:
            return client.chat.completions.create(model="demo", messages=[])
        except Exception:
            continue

from openai import OpenAI


def run():
    client = OpenAI()
    return client.chat.completions.create(model="demo", messages=[])

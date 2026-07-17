import groq


def run():
    return groq.chat.completions.create(model="demo", messages=[])

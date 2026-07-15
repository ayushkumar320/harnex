from openai import OpenAI


def run_agent() -> None:
    client = OpenAI()
    client.chat.completions.create(model="demo", messages=[])


if __name__ == "__main__":
    run_agent()

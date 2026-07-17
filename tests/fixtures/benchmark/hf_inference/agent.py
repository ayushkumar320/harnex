from huggingface_hub import InferenceClient


def run():
    client = InferenceClient()
    return client.text_generation("hello")

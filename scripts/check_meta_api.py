import os

from dotenv import load_dotenv
from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"


def main() -> None:
    load_dotenv()

    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError("MODEL_API_KEY is missing from .env")

    client = OpenAI(
        base_url=BASE_URL,
        api_key=api_key,
    )

    response = client.responses.create(
        model=MODEL,
        input="Reply with exactly: ProtocolSmith Meta connection successful",
    )

    print(response.output_text)


if __name__ == "__main__":
    main()


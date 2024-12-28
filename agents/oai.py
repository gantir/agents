from dotenv import load_dotenv
from dspy import OpenAI

load_dotenv()

client = OpenAI()
completion = client.chat.completions.create(
    model="gpt-4o",
    store=True,
    messages=[{"role": "user", "content": "write a haiku about ai"}],
)

import anthropic

# Takes the default token from the environment
client: anthropic.Anthropic = anthropic.Anthropic()

url: str = "https://contribute.cncf.io/contributors/projects/"
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    temperature=0.10,
    # system="You are a class 1 student. Respond to the content similarly",
    system="You are a program to transform data as requested by the user.",
    # messages=[
    #     {"role": "user", "content": "Hello, Claude"},
    #     {"role": "assistant", "content": "Hi, I'm Claude. How can I help you?"},
    #     {"role": "user", "content": "Can you explain LLMs in plain English?"},
    # ]
    # messages=[
    #     {"role": "user", "content": "What's the Greek name for Sun? (A) Sol (B) Helios (C) Sun"},
    #     # {"role": "assistant", "content": "The best answer is ("},
    # ]
    messages=[
        {"role": "user", "content": "Why is the ocean salty?"},
    ],
    tools=[
        {
            type: "function",
            "function": {
                "name": "extract_github_urls",
                "description": "Crawls a webpage and extracts all GitHub repository and user profile URLs. Supports depth-limited crawling and includes rate limiting and validation features.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The target URL to crawl for GitHub links",
                        },
                    },
                    "required": ["url"],
                },
            },
        }
    ],
)
print(message.content)

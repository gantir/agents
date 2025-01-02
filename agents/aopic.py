from pprint import pprint
from typing import Any

import anthropic

from agents.tools.github import GitHubRepo, get_repos


def run() -> None:
    url: str = "https://contribute.cncf.io/contributors/projects/"

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": f"Get all the projects from the CNCF contributors page with url {url} and present the total number of projects, format the output as csv which is excel safe along with summary of key observations and comments about the repos.",
        },
    ]

    tool_definitions: list[dict[str, Any]] = [
        {
            "name": "get_repos",
            "description": "Crawls a webpage and extracts all GitHub repository and user profile URLs. Supports depth-limited crawling and includes rate limiting and validation features.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The target URL to crawl for GitHub links",
                    },
                },
                "required": ["url"],
            },
        }
    ]

    # Takes the default token from the environment
    client: anthropic.Anthropic = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system="You are a program to transform data as requested by the user. You have access to tools, but only use them when necessary.  If a tool is not required, respond as normal",
        messages=messages,
        tools=tool_definitions,
    )

    # Appending the assitant response to the initial user message asking for the github projects mentioned on a page
    messages.append({"role": "assistant", "content": response.content})

    # pprint(messages)

    tool_use = response.content[1]
    tool_name: str = tool_use.name
    tool_inputs: dict[str, Any] = tool_use.input
    github_projects: list[Any] = []
    if "get_repos" == tool_name:
        github_projects = get_repos(**tool_inputs)

    tool_response: dict[str, Any] = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": GitHubRepo.schema().dumps(github_projects, many=True),
            }
        ],
    }
    messages.append(tool_response)

    # pprint(messages)

    follow_up_response = client.messages.create(
        model="claude-3-sonnet-20240229",
        messages=messages,
        max_tokens=1000,
        tools=tool_definitions,
    )

    pprint(follow_up_response.content)

import json
from pathlib import Path
import logging
import os
import asyncio
from functools import lru_cache
import random

import boto3
from jinja2 import Environment, FileSystemLoader
import typer
from pydantic import BaseModel

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
LOGGER = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_INFERENCE_PROFILE_ARN = os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")

PROMPT_DIR = Path(__file__).parent / "prompts/generate_summaries"
JINJA_ENV = Environment(loader=FileSystemLoader(PROMPT_DIR))

DEFAULT_OUTPUT_DIR = Path(__file__).parents[1] / "outputs"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", DEFAULT_OUTPUT_DIR))


class Event(BaseModel):
    event_description: str
    locations_mentioned: list[str]
    date: str
    citation: str


class Events(BaseModel):
    events: list[Event]
    path: str


BEDROCK_TOOLS = [
    {
        "toolSpec": {
            "name": "extract_events",
            "inputSchema": {
                "json": Events.model_json_schema()
            }
        }
    }
]


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    with open(os.path.join(PROMPT_DIR, "system.txt"), "r") as f:
        return f.read()


def _load_context(article: dict) -> str:
    return JINJA_ENV.get_template("context.jinja").render(
        article=article,
    )

async def _request_bedrock(
    system_prompt: str,
    context: str,
    max_retries: int = 5,
    initial_delay: float = 5.0
):
    bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    tool_config = {
        "tools": BEDROCK_TOOLS,
        "toolChoice": {
            "tool": {"name": "extract_events"},
        },
    }
    system = [
        {"text": system_prompt},
    ]
    messages = [
        {
            "role": "user",
            "content": [
                {"text": context},
                {"text": "Please use the extract_events tool to extract events from the article."}
            ]
        },
    ]
    LOGGER.debug(messages)
    retry_count = 0
    while True:
        try:
            response = bedrock_client.converse(
                modelId=BEDROCK_INFERENCE_PROFILE_ARN,
                messages=messages,
                system=system,
                toolConfig=tool_config,
            )
            return response
            
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                LOGGER.error(f"Max retries ({max_retries}) exceeded. Final error: {e}")
                raise  # Re-raise the last exception after max retries
                
            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retry_count - 1))  # Exponential backoff
            jitter = random.uniform(0, 0.1 * delay)  # Add 0-10% jitter
            total_delay = delay + jitter
            
            LOGGER.warning(
                f"Throttling error encountered (attempt {retry_count}/{max_retries}). "
                f"Retrying in {total_delay:.2f} seconds..."
            )
            
            # Wait before retrying
            await asyncio.sleep(total_delay)


def _parse_response(response: dict) -> Events:
    raw_output = response["output"]["message"]["content"][0]["toolUse"]["input"]
    events = Events(events=raw_output["events"], path=raw_output["path"])
    return events


async def infer(article: dict, output_dir: str) -> dict:

    system_prompt = _load_system_prompt()
    LOGGER.debug(system_prompt)
    context = _load_context(article)
    LOGGER.debug(context)
    LOGGER.info(f"Running inference for article: {article['path']}")
    response = await _request_bedrock(system_prompt, context)
    LOGGER.info(response)
    events = _parse_response(response)
    LOGGER.info(events)
    with open(output_dir / f"events_{article['path']}.json", "w") as f:
        json.dump(events.model_dump(mode="json"), f)
    return events.model_dump(mode="json")



async def _main(
    user_profile: str,
    topic_of_interest: str,
    articles_file: str,
    output_dir: str
):
    with open(articles_file, "r") as f:
        articles = json.load(f)
    inference_tasks = []
    for article in articles:
        inference_tasks.append(infer(article, output_dir))
    await asyncio.gather(*inference_tasks)


def main(user_profile: str, topic_of_interest: str, articles_file: str, output_dir: str):
    asyncio.run(_main(user_profile, topic_of_interest, articles_file, output_dir))


if __name__ == "__main__":

    typer.run(main)


import logging
import os
from pathlib import Path
import json
from functools import lru_cache
from pydantic import BaseModel

import boto3
import streamlit as st
from jinja2 import Environment, FileSystemLoader

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
LOGGER = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts/app"
JINJA_ENV = Environment(loader=FileSystemLoader(PROMPT_DIR))

DEFAULT_EVENTS_DIR = Path(__file__).parents[1] / "outputs"
EVENTS_DIR = Path(os.environ.get("EVENTS_DIR", DEFAULT_EVENTS_DIR))


AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_INFERENCE_PROFILE_ARN = os.getenv(
    "BEDROCK_INFERENCE_PROFILE_ARN",
)


class Event(BaseModel):
    event_description: str
    locations_mentioned: list[str]
    date: str
    path: str


class Report(BaseModel):
    title: str
    summary: str
    key_events: list[Event]
    key_implications: str


BEDROCK_TOOLS = [
    {
        "toolSpec": {
            "name": "create_report",
            "inputSchema": {
                "json": Report.model_json_schema()
            }
        }
    }
]


def _request_bedrock(
    system_prompt: str,
    context: str,
):
    bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    tool_config = {
        "tools": BEDROCK_TOOLS,
        "toolChoice": {
            "tool": {"name": "create_report"},
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
                {"text": "Please use the create_report tool to create a report."}
            ]
        },
    ]
    LOGGER.debug(messages)
    response = bedrock_client.converse(
                modelId=BEDROCK_INFERENCE_PROFILE_ARN,
                messages=messages,
                system=system,
                toolConfig=tool_config,
            )
    return response


@lru_cache(maxsize=1)
def _load_events() -> list[dict]:
    events = []
    for file in EVENTS_DIR.glob("events_detail*.json"):
        with open(file, "r") as f:
            events.append(json.load(f))
    processed_events = []
    for event in events:
        processed_event = {
            "path": event["path"],
            "events": [],
        }
        for e in event["events"]:
            processed_event["events"].append({
                "event_description": e["event_description"],
                "locations_mentioned": e["locations_mentioned"],
                "date": e["date"],
                "path": event["path"],
            })
        processed_events.append(processed_event)
    return processed_events


def _load_system_prompt(topic_of_interest: str) -> str:
    return JINJA_ENV.get_template("system.jinja").render(
        user_profile=user_profile,
        topic_of_interest=topic_of_interest,
    )


def _load_context(events: list[dict], topic_of_interest: str) -> str:
    return JINJA_ENV.get_template("context.jinja").render(
        events=events,
        topic_of_interest=topic_of_interest,
    )


st.set_page_config(
    page_title="Wood Mackenzie EIA Report Generator",
    page_icon=":chart_with_upwards_trend:",
    layout="wide"
)

st.title("Wood Mackenzie EIA Report Generator")

user_profile = st.text_input(
    "Enter your profile (e.g., 'natural gas supply chain analyst', 'APAC lithium mining analyst')"
)
topic_of_interest = st.text_input(
    "Enter your topic of interest (e.g., 'US shale production', 'lithium prices')"
)

events = _load_events()

system_prompt = _load_system_prompt(topic_of_interest)
context = _load_context(events, topic_of_interest)

if st.button("Generate Report"):
    with st.spinner("Generating report..."):
        report = _request_bedrock(system_prompt, context)
        st.write(report)

import time
import os
from pathlib import Path
from typing import Dict, Optional

import chainlit as cl
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential

from utils.utils import (
    append_message, init_settings, get_llm_details, get_llm_models, get_logger,
)
from utils.chats import chat_completion
from utils.foundry import chat_agent

logger = get_logger()

# Allowed users for the FileUploader (optional: empty means everyone)
ALLOWED_UPLOADER_USERS = os.getenv("ALLOWED_UPLOADER_USERS", "").split(",")
ALLOWED_UPLOADER_USERS = [email.strip() for email in ALLOWED_UPLOADER_USERS if email.strip()]

@cl.header_auth_callback
def header_auth_callback(headers: Dict) -> Optional[cl.User]:
    """Authenticate via Azure App Service headers."""
    user_name = headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "dummy@microsoft.com")
    user_id = headers.get("X-MS-CLIENT-PRINCIPAL-ID", "9876543210")
    logger.debug(f"Auth Headers: {headers}")

    if user_name:
        return cl.User(identifier=user_name, metadata={"role": "admin", "provider": "header", "id": user_id})
    return None


@cl.set_chat_profiles
async def chat_profile():
    """Expose chat profiles from configured LLM models."""
    llm_models = get_llm_models()
    model_list = [f"{model['model_deployment']}--{model['description']}" for model in llm_models]
    profiles = []
    for item in model_list:
        model_deployment, description = item.split("--", 1)
        profiles.append(
            cl.ChatProfile(
                name=model_deployment,
                markdown_description=description
            )
        )
    return profiles


@cl.set_starters
async def set_starters():
    """Starter prompts."""
    return [
        cl.Starter(
            label="Morning routine ideation",
            message="Can you help me create a personalized morning routine that would help increase my productivity throughout the day? Start by asking me about my current habits and what activities energize me in the morning.",
            icon="/public/bulb.webp",
        ),
        cl.Starter(
            label="Spot the errors",
            message="How can I avoid common mistakes when proofreading my work?",
            icon="/public/warning.webp",
        ),
        cl.Starter(
            label="Get more done",
            message="How can I improve my productivity during remote work?",
            icon="/public/rocket.png",
        ),
        cl.Starter(
            label="Boost your knowledge",
            message="Help me learn about [topic]",
            icon="/public/book.png",
        ),
    ]


@cl.on_chat_resume
async def on_chat_resume(thread):
    """Handle chat resumption (noop)."""
    pass


async def _post_start_init():
    """Shared initialization now called immediately on chat start."""
    try:
        cl.user_session.set("chat_settings", await init_settings())
        llm_details = get_llm_details()

        # Initialize Foundry thread eagerly if provider is 'foundry' and not yet created
        if cl.user_session.get("chat_settings").get("model_provider") == "foundry" and not cl.user_session.get("thread_id"):
            agents_client = AgentsClient(
                endpoint=llm_details["api_endpoint"],
                credential=DefaultAzureCredential(),
            )
            thread = agents_client.threads.create()
            cl.user_session.set("thread_id", thread.id)
            logger.info(f"New thread created, thread ID: {thread.id}")

    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}", author="Error").send()
        logger.error(f"Error: {str(e)}")


@cl.on_chat_start
async def start():
    """
    Initialize the chat session and immediately render the FileUploader
    (consent flow disabled).
    """
    Path(".files").mkdir(parents=True, exist_ok=True)

    # Run init now (no consent gate)
    await _post_start_init()

    # Current user email
    user = cl.user_session.get("user")
    user_email = user.identifier if user else None
    logger.info(f"user_email={user_email}")

    # Should this user see the uploader?
    show_uploader = (not ALLOWED_UPLOADER_USERS) or (user_email in ALLOWED_UPLOADER_USERS)
    logger.info(f"User: {user_email}, Show uploader: {show_uploader}")

    # Only send FileUploader if user is allowed
    if show_uploader:
        fupl = cl.CustomElement(
            name="FileUploader",
            display="inline",
            props={"userEmail": user_email},  # Pass user email as prop
        )
        fupl_msg = cl.Message(content="", elements=[fupl])
        await fupl_msg.send()


@cl.on_message
async def main(message: cl.Message):
    """
    Handle user messages and route to Foundry or the default chat completion.
    """
    try:
        cl.user_session.set("start_time", time.time())
        user_input = message.content

        # Gather message history (and any uploaded elements)
        messages = append_message("user", user_input, message.elements)

        # Route by provider
        provider = cl.user_session.get("chat_settings", {}).get("model_provider")
        if provider == "foundry":
            full_response = await chat_agent(user_input)
        else:
            full_response = await chat_completion(messages)

        # Save assistant message to history
        append_message("assistant", full_response)

    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}", author="Error").send()
        logger.error(f"Error: {str(e)}")

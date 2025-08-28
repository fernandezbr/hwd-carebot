# Chainlit application main entry point for BSP AI Assistant
# This file handles authentication, chat profiles, startup routines, and message processing
# Supporting both standard LLM providers via LiteLLM and Azure AI Foundry agents

import time
import chainlit as cl
from utils.utils import (
    append_message, init_settings, get_llm_details, get_llm_models, get_logger,
)
from typing import Dict, Optional
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from utils.chats import chat_completion
from utils.foundry import chat_agent

logger = get_logger()


@cl.header_auth_callback
def header_auth_callback(headers: Dict) -> Optional[cl.User]:
    """
    Handle authentication using headers from Azure App Service.
    
    Extracts user information from HTTP headers for authentication
    in Azure App Service environments.
    
    Args:
        headers: Dictionary containing HTTP request headers
        
    Returns:
        Optional[cl.User]: User object if authentication successful, None otherwise
    """
    # Verify the signature of a token in the header (ex: jwt token)
    # or check that the value is matching a row from your database
    user_name = headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'dummy@microsoft.com')
    user_id = headers.get('X-MS-CLIENT-PRINCIPAL-ID', '9876543210')
    logger.debug(f"Auth Headers: {headers}")

    if user_name:
        return cl.User(identifier=user_name, metadata={"role": "admin", "provider": "header", "id": user_id})
    else:
        return None


@cl.set_chat_profiles
async def chat_profile():
    """
    Set up available chat profiles based on configured LLM models.
    
    Creates chat profiles from the model configurations, allowing users
    to select different language models for their conversations.
    
    Returns:
        List[cl.ChatProfile]: List of available chat profiles
    """
    llm_models = get_llm_models()
    # get a list of model names from llm_models
    model_list = [f"{model["model_deployment"]}--{model["description"]}" for model in llm_models]
    profiles = []

    for item in model_list:
        model_deployment, description = item.split("--")

        # Create a profile for each model
        profiles.append(
            cl.ChatProfile(
                name=model_deployment,
                markdown_description=description
            )
        )

    return profiles


@cl.set_starters
async def set_starters():
    """
    Define starter conversation prompts for the chat interface.
    
    Provides pre-configured conversation starters to help users
    begin interactions with the AI assistant.
    
    Returns:
        List[cl.Starter]: List of starter conversation prompts
    """
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
            )
        ]


@cl.on_chat_resume
async def on_chat_resume(thread):
    """
    Handle chat resumption when a user returns to an existing conversation.
    
    Args:
        thread: The conversation thread being resumed
    """
    pass


@cl.on_chat_start
async def start():
    """
    Initialize the chat session and send a welcome message.
    
    Sets up chat settings, initializes Azure AI Foundry agents if needed,
    and prepares the conversation environment for the user.
    """
    try:
        cl.user_session.set("chat_settings", await init_settings())
        llm_details = get_llm_details()

        # Create an instance of the AgentsClient using DefaultAzureCredential
        if cl.user_session.get("chat_settings").get("model_provider") == "foundry" and not cl.user_session.get("thread_id"):
            agents_client = AgentsClient(
                # conn_str=llm_details["api_key"],
                endpoint=llm_details["api_endpoint"],
                credential=DefaultAzureCredential()
            )

            # Create a thread for the agent
            thread = agents_client.threads.create()
            cl.user_session.set("thread_id", thread.id)
            logger.info(f"New thread created, thread ID: {thread.id}")

    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}", author="Error").send()
        logger.error(f"Error: {str(e)}")


@cl.on_message
async def main(message: cl.Message):
    """
    Process incoming user messages and generate responses using configured LLM providers.
    
    Routes messages to either Azure AI Foundry agents or standard LLM providers
    based on the selected chat profile configuration.
    
    Args:
        message: The message object from Chainlit containing user's input and attachments
    """
    try:
        cl.user_session.set("start_time", time.time())
        user_input = message.content

        # Get messages from session
        messages = append_message("user", user_input, message.elements)

        if cl.user_session.get("chat_settings").get("model_provider") == "foundry":
            full_response = await chat_agent(user_input)
        else:
            full_response = await chat_completion(messages)

        # Save the complete message to session
        append_message("assistant", full_response)

    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}", author="Error").send()
        logger.error(f"Error: {str(e)}")

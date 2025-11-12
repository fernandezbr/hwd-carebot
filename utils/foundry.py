# Azure AI Foundry agent integration for BSP AI Assistant
# This file handles interactions with Azure AI Foundry agents
# Supporting advanced capabilities like code interpretation and file processing

import os
import time
import urllib.parse
import chainlit as cl
from typing import List
from pathlib import Path
from loguru import logger
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from utils.utils import get_llm_models
from azure.ai.agents.models import (
    CodeInterpreterTool,
    MessageAttachment,
    MessageInputContentBlock,
    MessageInputTextBlock,
    MessageImageFileParam,
    MessageInputImageFileBlock,
    FilePurpose,
    MessageRole,
    AgentStreamEvent,
    MessageDeltaChunk,
    ThreadRun,
)


# Chat with Azure AI Agents
async def chat_agent(user_input: str) -> str:
    """
    Generate a response from Azure AI Foundry agents with advanced capabilities.
    
    Handles file uploads, code interpretation, and streaming responses from
    Azure AI Foundry agents. Supports image generation and file annotations.
    
    Args:
        user_input: The user's message to send to the agent
        
    Returns:
        str: The agent's complete response text
        
    Raises:
        RuntimeError: If agent response generation fails
    """
    try:
        # Get chat settings
        chat_settings = cl.user_session.get("chat_settings")
        chat_profile = cl.user_session.get("chat_profile")
        model_name = chat_settings.get("model_name")        # Get the model details from the selected model
        llm_details = next((item for item in get_llm_models() if item["model_deployment"] == chat_profile), {})
        
        # Show thinking message to user
        msg = await cl.Message(f"[{model_name}] thinking...", author="agent").send()
        if not msg:
            raise Exception("Failed to create message object")

        # Create an instance of the AgentsClient using DefaultAzureCredential
        agents_client = AgentsClient(
            endpoint=llm_details["api_endpoint"],
            credential=DefaultAzureCredential()
        )

        thread_id = cl.user_session.get("thread_id")
        file_uploads = cl.user_session.get("file_uploads", [])
        file_contents = cl.user_session.get("file_contents", [])
        # content_blocks = user_input
        attachments = []
        content_blocks = [MessageInputTextBlock(text=user_input)]

        # Loop through file contents to append to content blocks
        for content in file_contents:
            content_blocks.append(MessageInputTextBlock(text=content))

        # Loop through file uploads to prepare content blocks and attachments
        for upload in file_uploads:
            logger.info(f"File upload: {upload}")

            # Upload a file and wait for it to be processed
            if upload["path"]:
                file = agents_client.files.upload_and_poll(
                    file_path=upload["path"], purpose=FilePurpose.AGENTS
                )
                logger.info(f"File ID: {file.id}")

                # Create a message with the attachment
                attachment = MessageAttachment(file_id=file.id, tools=CodeInterpreterTool().definitions)
                attachments.append(attachment)

                # If the file is an image, create a content block for it
                if upload["mime"].startswith("image/"):
                    file_param = MessageImageFileParam(file_id=file.id, detail="high")
                    content_blocks: List[MessageInputContentBlock] = [
                        MessageInputTextBlock(text=user_input),
                        MessageInputImageFileBlock(image_file=file_param),
                    ]

        logger.debug(f"Content blocks: {content_blocks}")
        logger.debug(f"Attachments: {attachments}")

        # Create a message, with the prompt being the message content that is sent to the model
        agents_client.messages.create(
            thread_id=thread_id,
            role="user",
            content=content_blocks,
            attachments=attachments
        )

        is_thinking = True        # Run the agent to process tne message in the thread
        with agents_client.runs.stream(thread_id=thread_id, agent_id=llm_details["model_id"]) as stream:
            msg.content = ""
            for event_type, event_data, _ in stream:
                if isinstance(event_data, MessageDeltaChunk):
                    msg.content += event_data.text
                    if msg:
                        await msg.update()

                    if is_thinking:
                        logger.info(f"Elapsed time: {(time.time() - cl.user_session.get('start_time')):.2f} seconds")
                        is_thinking = False

                elif isinstance(event_data, ThreadRun):
                    if event_data.status == "failed":
                        logger.error(f"Run failed. Error: {event_data.last_error}")
                        raise Exception(event_data.last_error)

                elif event_type == AgentStreamEvent.ERROR:
                    logger.error(f"An error occurred. Data: {event_data}")
                    raise Exception(event_data)

        # Get all messages from the thread
        messages = agents_client.messages.list(thread_id)
        images = []

        # Process the messages to extract image contents and file path annotations
        for message in messages:
            last_image = None
            # Save every image file in the message
            if message.image_contents:
                last_image = message.image_contents[-1]
                logger.info(f"Response message: {message}")

            if last_image and "file_id" in last_image:
                # If the last image has a file_id, save it to the current working directory
                file_id = last_image.file_id
                file_name = f"{file_id}_image_file.png"
                agents_client.files.save(file_id=file_id, file_name=file_name)
                image = cl.Image(path=f"{Path.cwd() / file_name}", name=file_name, display="inline")
                images.append(image)

        # Append the images to the message
        if len(images) > 0:
            msg.elements = images        # Get the last message from the agent

        response_message = agents_client.messages.get_last_message_text_by_role(thread_id=thread_id, role=MessageRole.AGENT)
        if not response_message:
            raise Exception("No response from the model.")

        # Start with the message text
        msg.content = response_message.text.value
        
        # Build a mapping of file_id to original filename
        file_uploads = cl.user_session.get("file_uploads", [])
        file_id_map = {}
        
        # Store uploaded files metadata for later retrieval
        file_id_mapping = cl.user_session.get("file_id_mapping")
        if not file_id_mapping:
            file_id_mapping = {}
            cl.user_session.set("file_id_mapping", file_id_mapping)

        # Process annotations to extract file information and clean up markers
        citation_sources = []
        
        for annotation in response_message.text.annotations:
            logger.info(f"Annotation: {annotation}")
            
            # Remove annotation markers from the text (e.g., 【9:0†source】)
            if hasattr(annotation, 'text') and annotation.text and isinstance(annotation.text, str):
                msg.content = msg.content.replace(annotation.text, '')
            
            # Handle URL citations (external web sources OR uploaded files)
            if "url_citation" in annotation:
                url_citation = annotation.url_citation
                title = url_citation.title
                url = url_citation.url
                
                # Check if this is actually a file reference (Azure uses doc_0, doc_1, etc. for uploaded files)
                if url and url.startswith('doc_'):
                    # This is a file reference, treat it as a file citation
                    sharepoint_url = None
                    try:
                        # Use fixed SharePoint base path. Allow override via SHAREPOINT_FIXED_PATH env var.
                        sp_base = os.getenv(
                            "SHAREPOINT_FIXED_PATH",
                            "https://bspgovph.sharepoint.com/:b:/r/sites/CMTEINNOVATIONLAB/Shared%20Documents/HWDInfoAsst/"
                        )
                        encoded_filename = urllib.parse.quote(title)
                        sharepoint_url = f"{sp_base}{encoded_filename}"
                        logger.info(f"Generated fixed SharePoint link for {title}: {sharepoint_url}")
                            
                    except Exception as e:
                        logger.error(f"Failed to generate SharePoint URL for {title}: {str(e)}")
                    
                    citation_sources.append({
                        'type': 'file',
                        'name': title,
                        'file_id': url,
                        'sharepoint_url': sharepoint_url
                    })
                else:
                    # This is an actual external URL
                    citation_sources.append({
                        'type': 'url',
                        'title': title,
                        'url': url
                    })
            
            # Handle file path citations (uploaded files like PDFs)
            elif "file_path" in annotation:
                file_citation = annotation.file_path
                file_id = file_citation.file_id
                
                # Try to find the original filename
                original_name = file_id_mapping.get(file_id) if file_id_mapping else None
                
                # If not in mapping, try to match from current uploads
                if not original_name:
                    for upload in file_uploads:
                        if upload.get("path"):
                            original_name = upload.get("name", f"Document")
                            # Store this mapping for future use
                            file_id_mapping[file_id] = original_name
                            cl.user_session.set("file_id_mapping", file_id_mapping)
                            break
                
                if not original_name:
                    original_name = f"Document"
                
                # Generate SharePoint direct link instead of downloading
                sharepoint_url = None
                try:
                    # Use fixed SharePoint base path. Allow override via SHAREPOINT_FIXED_PATH env var.
                    sp_base = os.getenv(
                        "SHAREPOINT_FIXED_PATH",
                        "https://bspgovph.sharepoint.com/:b:/r/sites/CMTEINNOVATIONLAB/Shared%20Documents/HWDInfoAsst/"
                    )
                    encoded_filename = urllib.parse.quote(original_name)
                    sharepoint_url = f"{sp_base}{encoded_filename}"
                    logger.info(f"Generated fixed SharePoint link for {original_name}: {sharepoint_url}")
                        
                except Exception as e:
                    logger.error(f"Failed to generate SharePoint URL for {file_id}: {str(e)}")
                
                citation_sources.append({
                    'type': 'file',
                    'name': original_name,
                    'file_id': file_id,
                    'sharepoint_url': sharepoint_url
                })

        # Append formatted citations at the end (deduplicated)
        if citation_sources:
            msg.content = msg.content.strip()  # Remove any trailing whitespace
            msg.content += "\n\n**Sources:**"
            
            # Deduplicate sources by name/title and URL
            seen_sources = set()
            
            for source in citation_sources:
                if source['type'] == 'url':
                    # Create unique key for URL citations
                    source_key = (source['type'], source['title'], source['url'])
                    if source_key not in seen_sources:
                        seen_sources.add(source_key)
                        msg.content += f"\n- [{source['title']}]({source['url']})"
                        
                elif source['type'] == 'file':
                    # Create unique key for file citations (by name and URL)
                    source_key = (source['type'], source['name'], source.get('sharepoint_url'))
                    if source_key not in seen_sources:
                        seen_sources.add(source_key)
                        # Use SharePoint URL if available, otherwise show file ID
                        if source.get('sharepoint_url'):
                            msg.content += f"\n- 📄 [{source['name']}]({source['sharepoint_url']})"
                        else:
                            msg.content += f"\n- 📄 **{source['name']}** (File ID: `{source['file_id']}`)"

        if msg:
            await msg.update()
        return msg.content

    except Exception as e:
        raise RuntimeError(f"Error generating response in chat_agent: {str(e)}")

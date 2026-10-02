"""
E2E test for conversation sidebar functionality.

Verifies:
1. Conversations are created when sending a chat message
2. Old conversations are retrieved from the API
3. Conversation IDs from the list match what the sidebar uses
4. The conversation detail endpoint returns the correct data for a given ID
5. Multiple messages in the same session belong to the same conversation
"""

from __future__ import annotations

import asyncio
import uuid

import aiohttp
import pytest


@pytest.mark.asyncio
async def test_e2e_conversations_sidebar_and_url():
    """E2E test: old conversations are retrieved and URL updates with conversation ID."""
    API_URL = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        username = f"e2e_{uuid.uuid4().hex[:8]}"
        password = "TestPass123!"

        # Step 1: Sign up a new user
        signup_resp = await session.post(
            f"{API_URL}/api/v1/auth/signup",
            json={"username": username, "password": password},
        )
        assert signup_resp.status == 201, f"Signup failed: {signup_resp.status}"
        signup_data = await signup_resp.json()
        token = signup_data["access_token"]
        user_id = signup_data["user_id"]

        # Step 2: List conversations (should be empty initially)
        list_resp = await session.get(
            f"{API_URL}/api/v1/chat/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_resp.status == 200
        list_data = await list_resp.json()
        conversations_before = list_data.get("conversations", [])
        assert len(conversations_before) == 0, "Expected no conversations before chat"

        # Step 3: Send a chat message (creates a conversation)
        chat_resp = await session.post(
            f"{API_URL}/api/v1/chat/stream",
            json={"message": "E2E test conversation"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert chat_resp.status == 200, f"Chat failed: {chat_resp.status}"

        # Wait for background persistence
        await asyncio.sleep(3)

        # Step 4: List conversations (should have 1)
        list_resp = await session.get(
            f"{API_URL}/api/v1/chat/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_resp.status == 200
        list_data = await list_resp.json()
        conversations = list_data.get("conversations", [])
        assert len(conversations) == 1, f"Expected 1 conversation, got {len(conversations)}"

        conversation_id = conversations[0]["id"]
        conversation_title = conversations[0]["title"]
        assert conversation_title == "E2E test conversation", "Expected correct conversation title"

        # Step 5: Get conversation by ID (simulates clicking in sidebar / URL update)
        detail_resp = await session.get(
            f"{API_URL}/api/v1/chat/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_resp.status == 200, f"Get conversation failed: {detail_resp.status}"
        detail_data = await detail_resp.json()
        assert detail_data["id"] == conversation_id, "ID mismatch in detail response"
        assert detail_data["title"] == conversation_title, "Title mismatch in detail response"
        # Each chat turn creates both a user message and an assistant response
        assert len(detail_data["messages"]) == 2, f"Expected 2 messages in conversation, got {len(detail_data['messages'])}"

        # Step 6: Send another message in the same session
        chat_resp2 = await session.post(
            f"{API_URL}/api/v1/chat/stream",
            json={"message": "Second message in same conversation"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert chat_resp2.status == 200
        await asyncio.sleep(3)

        # Step 7: Verify the conversation list still shows 1 conversation
        # (same session = same conversation)
        list_resp2 = await session.get(
            f"{API_URL}/api/v1/chat/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_resp2.status == 200
        list_data2 = await list_resp2.json()
        conversations2 = list_data2.get("conversations", [])
        assert len(conversations2) == 1, "Expected still 1 conversation (same session)"

        # Verify we can still access the conversation by ID
        detail_resp2 = await session.get(
            f"{API_URL}/api/v1/chat/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_resp2.status == 200
        detail_data2 = await detail_resp2.json()
        assert detail_data2["id"] == conversation_id, "Conversation not accessible by ID"
        # After second message: 2 user + 2 assistant = 4 messages total
        assert len(detail_data2["messages"]) == 4, f"Expected 4 messages in conversation, got {len(detail_data2['messages'])}"

        # Step 8: Reset session and create a new conversation
        reset_resp = await session.post(
            f"{API_URL}/api/v1/chat/reset",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Reset might fail if not implemented, that's ok
        if reset_resp.status != 200:
            pass

        # Send a message in a new session
        chat_resp3 = await session.post(
            f"{API_URL}/api/v1/chat/stream",
            json={"message": "New conversation after reset"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert chat_resp3.status == 200
        await asyncio.sleep(3)

        # Step 9: Verify we now have 2 conversations
        list_resp3 = await session.get(
            f"{API_URL}/api/v1/chat/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_resp3.status == 200
        list_data3 = await list_resp3.json()
        conversations3 = list_data3.get("conversations", [])
        assert len(conversations3) == 2, f"Expected 2 conversations after reset, got {len(conversations3)}"

        # Verify both conversations are accessible by their IDs
        conv_ids = [c["id"] for c in conversations3]
        assert conversation_id in conv_ids, "First conversation missing after reset"
        new_conv_id = [c["id"] for c in conversations3 if c["id"] != conversation_id][0]

        # Verify the first conversation still has its messages
        detail_resp3 = await session.get(
            f"{API_URL}/api/v1/chat/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_resp3.status == 200
        detail_data3 = await detail_resp3.json()
        # First conversation should still have 4 messages (2 turns)
        assert len(detail_data3["messages"]) == 4, "First conversation should still have 4 messages"

        print("✅ All E2E tests passed!")
        print(f"   First conversation ID: {conversation_id}")
        print(f"   First conversation URL: /chat/{conversation_id}")
        print(f"   Second conversation ID: {new_conv_id}")
        print(f"   Second conversation URL: /chat/{new_conv_id}")
        print(f"   Old conversations remain visible after reset: True")

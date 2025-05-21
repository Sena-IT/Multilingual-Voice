import os
from utils.constants import zoho_prompt
import openai
import json
import asyncio
from services.zoho.zoho import send_lead_to_zoho


def get_lead_data_with_llm(full_transcript: list) -> dict:
    try:
        # Set OpenAI API key from environment variables
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            print("❌ OpenAI API key is missing")
            return {"error": "OpenAI API key not found"}

        # Convert transcript to a string format
        transcript_text = "\n".join(
            f"{entry['role'].capitalize()}: {entry['content']}"
            for entry in full_transcript
            if entry.get('content')  # Skip entries without content
        )

        if not transcript_text or not isinstance(transcript_text, str):
            print("❌ Transcript text is empty or not a string")
            return {"error": "Invalid transcript input"}

        # Call OpenAI API
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": zoho_prompt},
                    {"role": "user", "content": transcript_text}
                ]
            )
        except Exception as e:
            print("❌ OpenAI API call failed:", e)
            return {"error": f"OpenAI API error: {str(e)}"}

        if not response or not response.choices:
            print("❌ Empty response from OpenAI")
            return {"error": "Empty response from LLM"}

        lead_result = response.choices[0].message.content

        if not lead_result:
            print("❌ LLM response content is None")
            return {"error": "No content returned from LLM"}

        # Parse JSON response
        try:
            lead_data = json.loads(lead_result)
        except json.JSONDecodeError as e:
            print("❌ JSON parsing error:", e)
            print("Raw LLM output:")
            print(lead_result)
            return {"error": "Invalid JSON returned from LLM"}

        # Extract payload (supports both {"data": {...}} and direct object)
        lead_payload = lead_data.get("data", lead_data)

        # Send to Zoho asynchronously
        try:
            asyncio.run(send_lead_to_zoho(lead_payload))
        except Exception as e:
            print("❌ Failed to send lead to Zoho:", e)

        return lead_data

    except Exception as e:
        print("❌ Unexpected exception during processing:", e)
        return {"error": str(e)}
import logging
import os
import requests
import httpx
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_new_access_token():
    print("enter the get_new_access_token function")
    url = "https://accounts.zoho.in/oauth/v2/token"
    data_1 = {
        "refresh_token": os.getenv("ZOHO_REFRESH_TOKEN"),
        "client_id": os.getenv("ZOHO_CRM_CLIENT_ID"),
        "client_secret": os.getenv("ZOHO_CRM_CLIENT_SECRET"),
        "grant_type": "refresh_token"
    }

    logger.info(f"🔍 Token request payload: {data_1}")
    response = requests.post(url, data=data_1)

    if response.status_code != 200:
        logger.error(f"❌ Token refresh failed: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to refresh Zoho token")

    try:
        result = response.json()
    except Exception:
        logger.error(f"❌ Error parsing token response: {response.text}")
        raise HTTPException(status_code=500, detail="Zoho token response is not JSON")

    access_token = result.get("access_token")
    if not access_token:
        logger.error("❌ access_token missing in response!")
        raise HTTPException(status_code=500, detail="Could not retrieve Zoho access token")

    logger.info(f"✅ Zoho access token retrieved successfully")
    return access_token


async def send_lead_to_zoho(lead):
    logger.info(f"📥 Lead received for submission: {lead}")
    print(f"lead\n", lead)

    access_token = get_new_access_token()
    if not access_token:
        raise HTTPException(status_code=500, detail="Could not retrieve Zoho access token")

    payload = {
        "data": [
            {
                "First_Name": lead["name"].split(" ", 1)[0],
                "Last_Name": lead["name"].split(" ", 1)[1] if len(lead["name"].split(" ", 1)) > 1 else ".",
                "Company": "Aladdin Holidays",
                "Email": lead["email"],
                "Phone": lead["whatsapp"],
                "Lead_Source": lead.get("source", "Website Form"),
                "Tour_Type": lead["tour_type"],
                "Location": lead["travel_location"],
                "Travels_Date": lead["travel_date"],
                "Days": str(lead["no_of_days"]),
                "Persons": str(lead["no_of_persons"])
            }
        ]
    }

    zoho_api_url = os.getenv("ZOHO_API_URL")
    if not zoho_api_url:
        raise HTTPException(status_code=500, detail="ZOHO_API_URL not configured")

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

    logger.info(f"📤 Sending lead to Zoho CRM: {payload}")
    print(f"📤 Sending lead to Zoho CRM: {payload}")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(zoho_api_url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"✅ Zoho CRM Response: {response_data}")
            print(f"✅ Zoho CRM Response: {response_data}")
            return response_data
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Zoho API error: {e.response.text} (Status {e.response.status_code})")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Zoho API error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"❌ Failed to send lead to Zoho CRM: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
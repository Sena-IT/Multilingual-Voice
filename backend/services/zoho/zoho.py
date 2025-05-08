def get_new_access_token():
    url = "https://accounts.zoho.in/oauth/v2/token"
    data = {
        "refresh_token": os.getenv("ZOHO_REFRESH_TOKEN"),
        "client_id": os.getenv("ZOHO_CRM_CLIENT_ID"),
        "client_secret": os.getenv("ZOHO_CRM_CLIENT_SECRET"),
        "grant_type": "refresh_token"
    }
 
    logging.info(f"🔍 Token request payload: {data}")
 
    response = requests.post(url, data=data)
 
    if response.status_code != 200:
        logging.error(f"❌ Token refresh failed: {response.text}")
        raise HTTPException(status_code=500, detail="Failed to refresh Zoho token")
 
    try:
        result = response.json()
    except Exception:
        logging.error(f"❌ Error parsing token response: {response.text}")
        raise HTTPException(status_code=500, detail="Zoho token response is not JSON")
 
    access_token = result.get("access_token")
    if not access_token:
        logging.error("❌ access_token missing in response!")
        raise HTTPException(status_code=500, detail="Could not retrieve Zoho access token")
 
    logging.info(f"✅ Zoho access token: {access_token}")
    return access_token
 

async def process_landing_page_lead(data, source: str):
    try:
        # # Step 1: Parse incoming JSON
        # lead_data = await request.json()
        # # logger.info(f"Received lead from {source}: {lead_data}")
 
        # # Step 2: Ensure 'source' is included in the data
        # lead_data_with_source = {**lead_data, "source": source}
        # # logger.info(f"Lead data with source added: {lead_data_with_source}")
 
        # # Step 3: Validate using Pydantic model
        # validated_data = LeadData(**lead_data_with_source)
        # # logger.info(f"Validated lead data: {validated_data.dict()}")
 
        # # Step 4: Save to text file
        # filename = save_to_text_file(validated_data.dict())
 
        # Step 5: Store to PostgreSQL
        conn, cur = get_db_cursor()
        try:
            cur.execute("""
                INSERT INTO leads (
                    name, email, whatsapp_number, travel_location,
                    travel_date, no_of_days, no_of_persons,
                    tour_type, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data["name"],
                data["email"],
                data["whatsapp"],
                data["travel_location"],
                data["travel_date"],
                data["no_of_days"],
                data["no_of_persons"],
                data["tour_type"],
                data["source"]
            ))
 
            return {"status": "success"}
            # lead_id = cur.fetchone()["id"]
            # # logger.info(f"Lead from {source} stored in DB with ID: {lead_id}")
 
            # # Step 6: Push to Zoho CRM
            # zoho_lead = ZohoLeadData(**validated_data.dict())
            # zoho_response = await send_lead_to_zoho(zoho_lead)
            # logger.info(f"Zoho CRM response for {source} lead: {zoho_response}")
 
            # Step 7: Return response
            # return {
            #     "status": "success",
            #     "message": f"Lead from {source} processed successfully",
            #     "lead_id": lead_id,
            #     "text_file": filename,
            #     "zoho_response": zoho_response,
            #     "data": validated_data.dict()
            # }
 
        except Exception as e:
            # logger.error(f"Error processing {source} lead: {str(e)}")
            # logger.error(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"Error: {str(e)}")
 
        finally:
            commit_changes(conn)
 
    except Exception as e:
        # logger.error(f"Error in {source} lead processing: {str(e)}")
        # logger.error(traceback.format_exc())  # ✅ Log full error trace
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")
 
 
async def send_lead_to_zoho(lead):
    print("lead\n",lead)
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
 
    url = os.getenv("ZOHO_API_URL")
    if not url:
        raise HTTPException(status_code=500, detail="ZOHO_API_URL not configured")
 
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    print(f"Sending lead to Zoho CRM: {payload}")
 
    logging.info(f"📤 Sending lead to Zoho CRM: {payload}")
 
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logging.info(f"✅ Zoho CRM Response: {response.json()}")
            print(f"✅ Zoho CRM Response: {response.json()}")
            return response.json()
    except httpx.HTTPStatusError as e:
        logging.error(f"❌ Zoho API error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Zoho API error: {e.response.text}")
    except Exception as e:
        logging.error(f"❌ Failed to send lead to Zoho CRM: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 
 
 
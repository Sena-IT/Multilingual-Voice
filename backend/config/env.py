import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
ZOHO_CRM_CLIENT_ID = os.getenv("ZOHO_CRM_CLIENT_ID")
ZOHO_CRM_CLIENT_SECRET = os.getenv("ZOHO_CRM_CLIENT_SECRET")
ZOHO_CRM_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")
ZOHO_CRM_REDIRECT_URL = os.getenv("ZOHO_CRM_REDIRECT_URL")
CODE=os.getenv("CODE")
ZOHO_CRM_ACCESS_TOKEN = os.getenv("ZOHO_ACCESS_TOKEN")
ZOHO_API_URL = os.getenv("ZOHO_API_URL")
ZOHO_AUTH_URL = os.getenv("ZOHO_AUTH_URL")


# Validate required environment variables
def validate_env():
    required_vars = ["OPENAI_API_KEY", "GOOGLE_API_KEY", "SARVAM_API_KEY",
                      "GROQ_API_KEY", "CARTESIA_API_KEY", "GLADIA_API_KEY",
                        "TOGETHER_API_KEY", "ZOHO_CRM_CLIENT_ID", "ZOHO_CRM_CLIENT_SECRET",
                          "ZOHO_CRM_REFRESH_TOKEN", "ZOHO_CRM_REDIRECT_URL", "CODE",
                            "ZOHO_CRM_ACCESS_TOKEN", "ZOHO_API_URL",
                              "ZOHO_AUTH_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}") 
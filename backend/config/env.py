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

# Validate required environment variables
def validate_env():
    required_vars = ["OPENAI_API_KEY", "GOOGLE_API_KEY", "SARVAM_API_KEY", "GROQ_API_KEY", "CARTESIA_API_KEY", "GLADIA_API_KEY", "TOGETHER_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}") 
import logging
import sys
from loguru import logger

def setup_logging():
    # Just return the logger without configuring it
    # This allows Pipecat to handle its own logging setup
    return logger
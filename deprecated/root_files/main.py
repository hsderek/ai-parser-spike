#!/usr/bin/env python3
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from src.cli import app

if __name__ == "__main__":
    sys.exit(app())

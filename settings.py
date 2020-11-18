import os
from dotenv import load_dotenv
load_dotenv()

TASK_API = os.getenv("TASK_API")
SIMILARITY_API = os.getenv("SIMILARITY_API")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

AGENTS_PATH = os.getenv("AGENTS_PATH")
TEMPLATES_PATH = os.getenv("TEMPLATES_PATH")

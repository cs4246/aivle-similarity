import os
from dotenv import load_dotenv
load_dotenv()

TASK_API = os.getenv("TASK_API")
SIMILARITY_API = os.getenv("SIMILARITY_API")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

AGENTS_PATH = '/home/course/cs4246/aivle-runner/agents'
TEMPLATES_PATH = 'templates'

from dotenv import load_dotenv
import os
from landingai_ade import LandingAIADE
from pathlib import Path

load_dotenv()

client = LandingAIADE()

response = client.parse(
    document=Path("cd.pdf"),
    model="dpt-2-latest"
)
print(response.chunks)

with open("output_CD.md", "w", encoding="utf-8") as f:
    f.write(response.markdown)
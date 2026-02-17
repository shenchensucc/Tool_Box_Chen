#!/usr/bin/env python3
"""Create .env from .env.example if it doesn't exist. Run from project root."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = root / ".env"
example = root / ".env.example"

if env.exists():
    print(".env already exists. Edit it to set AI_BUILDER_TOKEN.")
else:
    if example.exists():
        shutil.copy(example, env)
        print("Created .env from .env.example.")
        print("Edit .env and set AI_BUILDER_TOKEN=your_token_here")
        print("Get your token from AI Builders platform / MCP settings.")
    else:
        print("ERROR: .env.example not found.")

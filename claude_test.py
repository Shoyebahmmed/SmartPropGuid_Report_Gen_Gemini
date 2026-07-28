"""
claude_test.py
==============
Sanity check script -- the Claude equivalent of Shoeb's gemini_test.py.

Run this FIRST after setting up the API key to confirm Claude works,
before touching the full Streamlit app.

Usage:
    python claude_test.py

Expected:
    - Prints Claude's response to a simple Python question
    - Confirms auth, model access, and env-var loading all work

If this prints an answer, you're ready to run streamlit run app.py.
If it errors, fix auth here before wasting time debugging the full app.
"""

import os
import anthropic
from dotenv import load_dotenv

# Load environment variables from Cred.env or .env relative to this script's directory
# (same pattern Shoeb uses in gemini_test.py, keeps consistency)
script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, "Cred.env")
env_path = os.path.join(script_dir, ".env")

if os.path.exists(cred_path):
    load_dotenv(cred_path)
else:
    load_dotenv(env_path)

# Retrieve the API key from the environment
api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
if not api_key:
    raise ValueError(
        "ANTHROPIC_API_KEY environment variable not found. "
        "Please set it in your system/shell environment or create a local .env file."
    )

# Model choice -- Sonnet 4.6 is our default (cheap + high quality)
# Override via CLAUDE_MODEL env var if desired
model_name = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"

# Initialise the client
client = anthropic.Anthropic(api_key=api_key)


def ask_claude(prompt):
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate all text blocks in the response
        return "".join(block.text for block in response.content if hasattr(block, "text"))
    except Exception as e:
        return f"An error occurred: {e}"


if __name__ == "__main__":
    user_input = "Explain the difference between a list and a tuple in Python."
    print(f"Model: {model_name}")
    print(f"Key:   {api_key[:8]}...{api_key[-4:]}")
    print("\nClaude's Response:")
    print(ask_claude(user_input))

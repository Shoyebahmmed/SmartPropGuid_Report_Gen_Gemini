import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from Cred.env or .env relative to this script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, "Cred.env")
env_path = os.path.join(script_dir, ".env")

if os.path.exists(cred_path):
    load_dotenv(cred_path)
else:
    load_dotenv(env_path)

# Retrieve the API key from the environment
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError(
        "GEMINI_API_KEY environment variable not found. "
        "Please set it in your system/shell environment or create a local .env file."
    )

genai.configure(api_key=api_key)

# 2. Initialize the model
# 'gemini-2.5-flash' is the default recommended model.
model = genai.GenerativeModel('gemini-2.5-flash')

def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    user_input = "Explain the difference between a list and a tuple in Python."
    print(f"Gemini's Response:\n{ask_gemini(user_input)}")

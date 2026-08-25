"""
claude_client.py
================
Drop-in replacement for Shoeb's Gemini call in app.py.

Matches his exact pattern:
    response = genai.GenerativeModel('gemini-2.5-flash').generate_content(full_prompt)
    clean_html = response.text.strip()

Becomes:
    clean_html = generate_html_report(full_prompt)

That's it. One line change in his generate button block.
"""

import os
import anthropic

API_KEY = None
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "16000"))


SYSTEM_PROMPT = """You are a professional property analyst writing reports for
first-time home buyers in Australia (VIC and NSW).

CRITICAL RULES:
1. Never present fabricated precision as verified fact. When a data point isn't
   backed by the supplied Source Data, give a clearly-scoped, reasonable estimate
   instead ("typically around...") rather than inventing a suspiciously exact
   figure -- but always give a usable number so the report doesn't read as empty.
   Only write "data not available" when no reasonable estimate can be inferred
   from the inputs at all.
2. Return ONLY the exact HTML fragment the compiling instructions ask for -- no
   more, no less. Some requests want a full document (<!DOCTYPE html> ... </html>);
   others want only specific page divs. Follow whatever boundary the
   instructions specify. NO markdown fences (no ```html), NO preamble, NO
   explanation outside the HTML.
3. Preserve the template's structure, CSS classes, and layout exactly.
   Only replace placeholder values with real data.
4. This report is read directly by the client, not another analyst. Plain,
   warm, everyday English -- no investor jargon ("ROI compression", "yield
   decompression"), no unexplained acronyms. Every number, score, or
   recommendation needs a short plain-English reason attached to it explaining
   what it means for THIS buyer -- never leave a bare figure to speak for itself.
5. Be honest about affordability. If the budget doesn't match the market,
   say so clearly.
6. State-aware advice:
   - VIC: FHOG for new builds <$750k, stamp duty exemption <$600k full /
     $600-750k partial, Home Guarantee cap $950k Melbourne.
   - NSW: FHBAS full stamp duty exemption <$800k, Home Guarantee cap $900k Sydney.
"""


def generate_html_report(full_prompt):
    """
  
    Send Shoeb's already-built full_prompt to Claude, return clean HTML.
    Reads API key fresh on each call so dotenv loading order doesn't matter.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to Cred.env or .env."
        )

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": full_prompt}],
    )

    html = ""
    for block in response.content:
        if hasattr(block, "text"):
            html += block.text

    html = html.strip()
    if html.startswith("```html"):
        html = html[7:]
    elif html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]

    return html.strip()

# ---------------------------------------------------------------------------
# Smoke test -- run: python claude_client.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model: {MODEL}")
    print(f"Key:   {API_KEY[:8]}...{API_KEY[-4:] if API_KEY else 'MISSING'}")

    if not API_KEY:
        print("\nERROR: Set ANTHROPIC_API_KEY first.")
        raise SystemExit(1)

    test_prompt = """You are a professional property investment analyst assistant.
    You must populate the HTML report template provided below based on the following Inputs.

    --- INPUTS ---
    1. Property Type Preference: House
    2. Target Suburb/Area: Cheltenham VIC 3192
    3. Budget: $800k - $1.2M
    4. Purchase Intention: Live in
    5. Key Client Priorities: Good schools, Close to train station
    6. Pre-Sales Operator Instructions: Keep it under 500 words for demo.

    7. Source Data: No listing data uploaded.

    --- HTML REPORT TEMPLATE ---
    <!DOCTYPE html>
    <html><body>
    <h1>{{ suburb }} Report</h1>
    <p>{{ executive_summary }}</p>
    <p>{{ market_analysis }}</p>
    </body></html>

    --- COMPILING INSTRUCTIONS ---
    Return ONLY the complete HTML. No markdown fences.
    """

    result = generate_html_report(test_prompt)
    print("\n--- OUTPUT ---")
    print(result[:1200])
    print(f"\n[Total length: {len(result)} chars]")

# Exact Patch — Shoeb's `app.py` → Claude + HtAG + ABS

**Based on reading his real `app.py` (938 lines, commit as of Jul 28 2026).**

Only **4 tiny edits** to his `app.py`. Everything else stays.

---

## Step 1 — Update `requirements.txt`

```diff
- google-generativeai
+ anthropic>=0.40.0
+ requests>=2.31.0
```

Then `pip install -r requirements.txt` in his venv.

---

## Step 2 — Update `Cred.env`

He uses `Cred.env` (falls back to `.env`). Add:

```diff
- GEMINI_API_KEY=AIza...
+ ANTHROPIC_API_KEY=sk-ant-api03-...
+ HTAG_API_KEY=sk-project--...
+ CLAUDE_MODEL=claude-sonnet-4-6
```

---

## Step 3 — Edit `app.py` — four surgical changes

### Change 1: Line 7 — swap Gemini import

**Find:**
```python
import google.generativeai as genai
```

**Replace with:**
```python
from claude_client import generate_html_report
from htag_client import fetch_suburb, AmbiguousSuburb
from abs_client import fetch_census_medians
```

### Change 2: Lines 41–46 — swap API key setup

**Find:**
```python
# Initialize Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("⚠️ GEMINI_API_KEY not found in Cred.env or system environment. Please configure it to enable AI generation.")
```

**Replace with:**
```python
# Initialize Anthropic Claude API
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    st.warning("⚠️ ANTHROPIC_API_KEY not found in Cred.env or system environment. Please configure it to enable AI generation.")

# HtAG for live data (optional)
htag_key = os.environ.get("HTAG_API_KEY")
if not htag_key:
    st.info("ℹ️ HTAG_API_KEY not set — live suburb fetch will be disabled. CSV upload still works.")
```

### Change 3: Line 742 — update the error banner

**Find:**
```python
if not api_key:
    st.error("❌ Cannot generate report: Gemini API key is missing. Please add it to your Cred.env file.")
```

**Replace with:**
```python
if not api_key:
    st.error("❌ Cannot generate report: Anthropic API key is missing. Please add ANTHROPIC_API_KEY to your Cred.env file.")
```

### Change 4: Lines 846–865 — swap the actual model call

This is the important one. **Find this block** (starts around line 846):

```python
loader_placeholder = start_loader("AI is analyzing data and populating report layout…")
try:
    # Request model completion
    response = genai.GenerativeModel('gemini-2.5-flash').generate_content(full_prompt)
    
    # Store output in session state
    clean_html = response.text.strip()
    # Clean markdown code fences if model accidentally output them
    if clean_html.startswith("```html"):
        clean_html = clean_html[7:]
    if clean_html.endswith("```"):
        clean_html = clean_html[:-3]
    clean_html = clean_html.strip()
    
    st.session_state.generated_report_html = clean_html
    st.success("✅ Report generated successfully!")
except Exception as e:
    st.error(f"Failed to generate report from Gemini API: {e}")
finally:
    stop_loader(loader_placeholder)
```

**Replace with:**

```python
loader_placeholder = start_loader("Claude is analyzing data and populating report layout…")
try:
    # Request Claude completion (handles fence stripping internally)
    clean_html = generate_html_report(full_prompt)

    st.session_state.generated_report_html = clean_html
    st.success("✅ Report generated successfully!")
except Exception as e:
    st.error(f"Failed to generate report from Claude API: {e}")
finally:
    stop_loader(loader_placeholder)
```

**That's it for the required changes.** The app now runs on Claude.

---

## Step 4 — Add live HtAG fetch (recommended, optional)

Between lines 800 and 815, where `data_context` is being built, insert HtAG enrichment. **Find:**

```python
# Prepare instructions and data details to inject into Gemini prompt
data_context = ""
source_data_rows = ""
if df_filtered is not None and len(df_filtered) > 0:
    data_context = f"Manual Listings Data Compiled (Filtered for Postcode {postcode_str}):\n{df_filtered.to_string(index=False)}"
```

**Insert BEFORE that block:**

```python
# --- NEW: Live HtAG + ABS enrichment ---
htag_context = ""
if htag_key and suburb_input:
    try:
        pt = "unit" if st.session_state.get("property_type", "") in ("Unit", "Apartment") else "house"
        live_data = fetch_suburb(suburb_input, property_type=pt)
        if not live_data.get("error"):
            summary = live_data.get("summary", {})
            scores = live_data.get("scores", {})
            census = live_data.get("census", {})
            cash = live_data.get("cash_rate", {})
            htag_context = f"""

LIVE HtAG DATA for {suburb_input}:
- Typical price: ${summary.get('typical_price', 'n/a')}
- Median rent: ${summary.get('rent', 'n/a')}/week
- Gross yield: {(summary.get('gross_yield', 0) or 0) * 100:.2f}%
- Confidence: {summary.get('confidence', 'n/a')}
- Data period: {summary.get('period_end', 'n/a')}
- Adult population: {summary.get('adult_population', 'n/a')}
- Total dwellings: {summary.get('estimated_dwellings', 'n/a')}
- RCS Overall: {scores.get('rcs_overall', 'n/a')}
- RCS Lower Risk: {scores.get('rcs_lower_risk', 'n/a')}
- RCS Capital Growth: {scores.get('rcs_capital_growth', 'n/a')}
- Current RBA cash rate: {cash.get('cash_rate_pct', 'n/a')}% (as of {cash.get('date', 'n/a')})
- Median age: {census.get('median_age_persons', 'n/a')}
- Average household size: {census.get('average_household_size', 'n/a')}
"""
            st.success(f"✅ Live HtAG data loaded for {suburb_input}")
        else:
            st.warning(f"⚠️ HtAG: {live_data['error']}")
    except AmbiguousSuburb as ambig:
        candidates = ", ".join(f"{c['locality']} {c['state_name']} {c['postcode']}" for c in ambig.candidates)
        st.warning(f"⚠️ Suburb '{suburb_input}' is ambiguous. Try one of: {candidates}")
    except Exception as e:
        st.warning(f"⚠️ HtAG fetch failed: {e}")
# --- END NEW ---
```

Then **modify** the existing `full_prompt` string (around line 819) to include the HtAG context. Find where he lists the inputs:

```python
7. Source Data:
{data_context}
```

**Change to:**

```python
7. Source Data:
{data_context}
{htag_context}
```

Now Claude sees both the CSV rows AND the live HtAG numbers if they were fetched.

---

## Step 5 — Test in order

```powershell
# Set env vars in PowerShell
$env:ANTHROPIC_API_KEY='sk-ant-api03-...'
$env:HTAG_API_KEY='sk-project--...'
$env:CLAUDE_MODEL='claude-sonnet-4-6'

# 1. Sanity check the Claude client
python claude_client.py
# expect: printed HTML output

# 2. Run Shoeb's app
streamlit run app.py
```

In the app:
- Fill in the intake form (Full Name, Phone, Email, Suburb, etc)
- **Suburb input:** try `Cheltenham VIC` or `3192`
- Property type: House
- Budget: $800k - $1.2M
- Click Generate — you should see the Claude spinner, then a report

If HtAG fetch works, you'll see the ✅ success message in Step 4's new block.

---

## Summary of files

Copy these into Shoeb's repo root (same folder as `app.py`):

| File | What it does | Status |
|---|---|---|
| `claude_client.py` | Wraps Claude API | ✅ Required |
| `htag_client.py` | Live HtAG suburb data | ✅ Required if using live fetch |
| `abs_client.py` | Free ABS census | ⚠️ Optional (v1.1) |

---

## What Shoeb keeps

Every one of these stays exactly as he wrote them:

- Streamlit UI, dark/light theme system
- Intake form (11 priority checkboxes, all form fields)
- CSV / Excel upload logic
- `filter_property_data()` function
- Postcode auto-discovery from `C:\Users\ahmma\Desktop\Property_Data_Split`
- HTML template upload / default template loading
- Playwright PDF rendering with header/footer
- Base64 data URI conversion for LOGO.svg and House.png
- Session state management

Nothing gets rewritten. Only the LLM call swaps.

---

## Cost expectations

- Sonnet 4.6 default: **~$0.02 per report**
- Sonnet 4.5 fallback: `CLAUDE_MODEL=claude-sonnet-4-5` — same tier
- Opus 4.7 if you want top quality: `CLAUDE_MODEL=claude-opus-4-7` — ~$0.20 per report
- Haiku 4.5 for cheapest: `CLAUDE_MODEL=claude-haiku-4-5` — ~$0.003 per report but lower quality

Your $20 Anthropic credit = 1,000 Sonnet reports before topping up.

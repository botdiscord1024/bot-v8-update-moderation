import asyncio
import time
import os
from datetime import date
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

MAX_CALLS_PER_DAY = 200

# ── Internal State ────────────────────────────────────────
_calls_today = 0
_today_date = date.today()

# List keeping track of timestamps for requests sent within the rolling window
_request_history = []
_lock = asyncio.Lock()

def _reset_daily_if_needed():
    global _calls_today, _today_date
    today = date.today()
    if today != _today_date:
        _calls_today = 0
        _today_date = today

async def ask_gemini(contents, system=None, model_name="gemini-2.5-flash"):
    global _calls_today, _request_history
    
    async with _lock:
        _reset_daily_if_needed()
        
        # 1. Global daily limit check
        if _calls_today >= MAX_CALLS_PER_DAY:
            print("❌ Gemini Guard: Daily limit reached!")
            return "⚠️ The daily limit for AI requests has been reached."
        
        # 2. Rolling 30-second window check (max 10 requests per 30 seconds)
        now = time.time()
        _request_history = [t for t in _request_history if now - t < 30]
        
        if len(_request_history) >= 10:
            print(f"⚠️ Gemini Guard: Too many requests ({len(_request_history)} within 30s!). Rate-limiting...")
            return "⏱️ The system is currently busy. Please try again in a few seconds!"

        _request_history.append(now)
        _calls_today += 1

    # 3. Direct execution via gemini-2.5-flash
    try:
        kwargs = {"model_name": model_name}
        if system:
            kwargs["system_instruction"] = system
            
        model = genai.GenerativeModel(**kwargs)
        response = await asyncio.to_thread(model.generate_content, contents)
        return response.text.strip()

    except Exception as e:
        print(f"❌ Gemini Guard Core Error: {e}")
        return "⚠️ Failed to connect to the AI core. Please try again later."

def get_stats() -> dict:
    """Returns active stats for the /ai_status command"""
    _reset_daily_if_needed()
    now = time.time()
    active_in_30s = len([t for t in _request_history if now - t < 30])
    return {
        "calls_today": _calls_today,
        "calls_this_min": active_in_30s,
        "daily_limit": MAX_CALLS_PER_DAY
    }

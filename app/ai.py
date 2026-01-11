from __future__ import annotations
import json
from typing import List, Optional
from openai import OpenAI
from .settings import settings
from .models import Category

def _client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def choose_category(categories: List[Category], subject: str, snippet: str, body_text: str) -> Optional[str]:
    if not categories:
        return None
    prompt = {
        "task": "Choose the best category for this email based on category name+description. Return JSON only.",
        "categories": [{"name": c.name, "description": c.description} for c in categories],
        "email": {"subject": subject or "", "snippet": snippet or "", "body_text": (body_text or "")[:4000]},
        "output": {"category_name": "string from categories.name or null"},
    }
    resp = _client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role":"user","content":json.dumps(prompt)}],
        response_format={"type":"json_object"},
        temperature=0,
    )
    data = json.loads(resp.choices[0].message.content)
    name = data.get("category_name")
    if name and any(c.name == name for c in categories):
        return name
    return None

def summarize_email(subject: str, from_email: str, body_text: str) -> str:
    prompt = {
        "task": "Summarize the email for a busy user. Keep it short and actionable.",
        "email": {"from": from_email or "", "subject": subject or "", "body_text": (body_text or "")[:6000]},
        "output": "Return 2-4 bullet points, plain text.",
    }
    resp = _client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role":"user","content":json.dumps(prompt)}],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()

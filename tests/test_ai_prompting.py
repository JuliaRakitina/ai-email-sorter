import json
import types
from app import ai

class DummyResp:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=content))]

def test_choose_category_valid(monkeypatch):
    class C: 
        def __init__(self, name, description): self.name=name; self.description=description
    cats = [C("Work", "client and project"), C("Bills", "invoices and receipts")]

    def fake_create(**kwargs):
        return DummyResp(json.dumps({"category_name":"Bills"}))

    monkeypatch.setattr(ai, "_client", lambda: types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=fake_create))))
    picked = ai.choose_category(cats, "Invoice", "paid", "invoice attached")
    assert picked == "Bills"

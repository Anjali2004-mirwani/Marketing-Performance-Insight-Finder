import json
from http.server import BaseHTTPRequestHandler
from google import genai
from google.genai import types

_client = genai.Client()  # reads GEMINI_API_KEY automatically


def ask(system, user, tokens=2000):
    r = _client.models.generate_content(
        model="gemini-2.5-flash", contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json",
            max_output_tokens=tokens, thinking_config=types.ThinkingConfig(thinking_budget=0)))
    return json.loads(r.text)


SYSTEM = """You are a careful marketing analyst. You receive computed metric changes and correlations.
Rules:
- Use ONLY the numbers provided. Never invent or recalculate figures.
- Never claim causation. Use wording like "may be related", "worth checking".
- Only cover metrics with an absolute change of 10% or more.
- Possible drivers must come from the provided correlations or from clearly labelled hypotheses.
- Give 2 concrete next checks per metric.
Return ONLY JSON: {"headline":"","insights":[{"metric":"","finding":"","possible_drivers":[""],"next_checks":["",""]}]}"""


class handler(BaseHTTPRequestHandler):
    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("content-length", 0) or 0)) or b"{}")
        except ValueError:
            return self.send(400, {"error": "Invalid JSON"})
        items = d.get("items")
        if not isinstance(items, list) or not items:
            return self.send(400, {"error": "No metrics"})
        try:
            ai = ask(SYSTEM, json.dumps({"items": items, "correlations": d.get("correlations", [])}), 1500)
            valid = {i["metric"] for i in items}
            ai["insights"] = [i for i in ai.get("insights", []) if i.get("metric") in valid]  # drop invented metrics
            self.send(200, ai)
        except Exception as e:
            self.send(500, {"error": str(e)})
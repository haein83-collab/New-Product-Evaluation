from http.server import BaseHTTPRequestHandler
import json
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def search_with_claude(product_name: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""당신은 신제품 시장 조사 전문가입니다.
"{product_name}" 제품/소재에 대해 아래 13개 항목을 임원 보고용으로 조사해주세요.
각 항목은 **2~3문장**, 핵심 수치와 사실 중심으로 간결하게 작성하세요.

반드시 JSON 형식으로만 응답 (설명 없이):
{{
  "raw_material": "원료/소재 정보",
  "manufacturing": "제조방법/공정",
  "spec": "핵심 물성·스펙",
  "usage": "실제 사용처",
  "diff": "기존 제품과의 차이",
  "competitors": "주요 생산업체",
  "market_trend": "시장동향(가격·수요)",
  "customer_needs": "고객사 개발 니즈",
  "commercialization": "상용화 포인트/과제",
  "profitability": "수익성",
  "market_size": "시장규모/추정근거",
  "growth": "성장근거",
  "difficulty": "개발 난이도"
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not ANTHROPIC_API_KEY:
            self._respond(500, {"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        product_name = body.get("product_name", "").strip()
        if not product_name:
            self._respond(400, {"error": "product_name이 필요합니다."})
            return
        result = search_with_claude(product_name)
        self._respond(200, {"success": True, "data": result})

    def do_OPTIONS(self):
        self._respond(200, {})

    def _respond(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

from http.server import BaseHTTPRequestHandler
import json
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

FIELD_LABELS = {
    "raw_material": "원료/소재", "manufacturing": "제조방법", "spec": "핵심 물성·스펙",
    "usage": "사용처", "diff": "기존 제품과의 차이", "competitors": "주요 경쟁사",
    "market_trend": "시장동향", "customer_needs": "고객 니즈",
    "commercialization": "상용화 과제", "profitability": "수익성",
    "market_size": "시장규모", "growth": "성장근거", "difficulty": "개발 난이도",
}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not ANTHROPIC_API_KEY:
            self._respond(500, {"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        product_name = body.get("product_name", "제품명 미입력")
        step2 = body.get("step2", {})

        context = "\n".join(
            f"[{FIELD_LABELS.get(k, k)}] {v}"
            for k, v in step2.items() if v and str(v).strip()
        ) or "기초 자료 없음"

        prompt = f"""당신은 신제품 기획 전문가입니다.
아래는 "{product_name}"에 대한 기초 조사 자료입니다.

{context}

위 자료를 바탕으로 아래 5개 평가 항목에 대해 각각 점수(1·3·5점 중 하나)와 평가 사유(2~3문장)를 작성하세요.

평가 기준:
- barrier (진입장벽/공급제한): 5점=복수 장벽으로 모방 사실상 불가·공급사 극소수, 3점=장벽 일부 존재하나 2~3년 내 모방 가능, 1점=쉽게 모방 가능·진입장벽 없음
- painpoint (고객 Pain Point): 5점=핵심 문제 해결·프리미엄 지불 의향 높음, 3점=일부 해결하나 없어도 무방, 1점=해결 근거 부족·지불 의향 불확실
- market (시장규모/성장성): 5점=구체적 데이터 기반·고성장 기대, 3점=규모 제시되나 근거 부족·성장률 보통, 1점=규모 근거 미흡·성장 불분명
- profit (고마진/가격결정력): 5점=가격결정권 보유·고마진·성장기 초입, 3점=평균 마진·가격 경쟁 가능성 있음·성숙기, 1점=저마진 예상·시장 축소
- feasibility (실현 가능성): 5점=역량 충분 활용·계획 구체적·현실적, 3점=일부 연계 가능·일정 추상적, 1점=역량 연계 불분명·계획 부족

반드시 아래 JSON 형식으로만 응답하세요 (설명 없이 JSON만):
{{
  "barrier":     {{"score": 3, "reason": "평가 사유..."}},
  "painpoint":   {{"score": 5, "reason": "평가 사유..."}},
  "market":      {{"score": 3, "reason": "평가 사유..."}},
  "profit":      {{"score": 3, "reason": "평가 사유..."}},
  "feasibility": {{"score": 3, "reason": "평가 사유..."}}
}}"""

        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())

        for key in result:
            s = int(result[key].get("score", 3))
            result[key]["score"] = 5 if s >= 5 else (1 if s <= 1 else 3)

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

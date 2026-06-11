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

Non-Commodity 판정 조건: ① (진입장벽 O 또는 공급제한 O) — OR 조건 AND ② 고객 Pain Point O AND ③ 시장규모/성장성 O. 이 3가지를 모두 충족해야 Non-Commodity. 결과(수익성)는 참고용.

위 자료를 바탕으로 아래 6개 항목을 평가하세요.
- 결과는 반드시 O, △, X 중 하나
- 사유는 2~3문장, 구체적 근거 포함

항목:
1. nc_barrier (진입장벽): 기술/설비/원료/품질/환경규제 장벽 존재, 모방 난이도 높음
2. nc_supply (공급제한): 공급자 제한적, 단기간 내 대체재 출현 가능성 낮음
3. nc_pain (고객 Pain Point): 고객의 중요한 문제 해결, 미충족 니즈 충족, 프리미엄 지불 의사
4. nc_market (시장규모/성장성): 경제성 있는 시장규모, 중장기 성장성 보유
5. nc_margin (고마진/가격결정력): 당사 평균 이상 수익성, 고객 지불의사 존재
6. nc_lifecycle (Life Cycle): 성장기 사이클 또는 안정적 중장기 수익 가능

판정 기준: O=해당·명확, △=부분 해당·불확실, X=미해당

반드시 아래 JSON 형식으로만 응답 (설명 없이):
{{
  "nc_barrier":   {{"result": "O", "reason": "..."}},
  "nc_supply":    {{"result": "O", "reason": "..."}},
  "nc_pain":      {{"result": "△", "reason": "..."}},
  "nc_market":    {{"result": "O", "reason": "..."}},
  "nc_margin":    {{"result": "△", "reason": "..."}},
  "nc_lifecycle": {{"result": "O", "reason": "..."}}
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

        valid = {"O", "△", "X"}
        for key in result:
            if result[key].get("result") not in valid:
                result[key]["result"] = "△"

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

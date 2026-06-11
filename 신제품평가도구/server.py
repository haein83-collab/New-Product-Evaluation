"""
신제품 평가 시스템 - 백엔드 서버

현재: SerpAPI 검색 + Claude Haiku 요약
나중에 전체를 Anthropic으로 교체하려면:
  SEARCH_ENGINE = "anthropic" 으로 변경
"""

import os
import sys
import json
import re

# Windows 콘솔 UTF-8 출력
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app)

# ─── 설정 ────────────────────────────────────────────────
SEARCH_ENGINE     = "anthropic"   # "serp" 또는 "anthropic"
SERP_API_KEY      = os.environ.get("SERP_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# ─────────────────────────────────────────────────────────

FIELD_LABELS = {
    "raw_material":      "원료/소재 정보",
    "manufacturing":     "제조방법/공정",
    "spec":              "핵심 물성·스펙",
    "usage":             "실제 사용처",
    "diff":              "기존 제품과의 차이",
    "competitors":       "주요 생산업체",
    "market_trend":      "시장동향(가격·수요)",
    "customer_needs":    "고객사 개발 니즈",
    "commercialization": "상용화 포인트/과제",
    "profitability":     "수익성",
    "market_size":       "시장규모/추정근거",
    "growth":            "성장근거",
    "difficulty":        "개발 난이도",
}


# ── SerpAPI 검색 ──────────────────────────────────────────
def serp_search(query, num=4):
    """SerpAPI 구글 검색 → 스니펫 텍스트 목록 반환"""
    from serpapi import GoogleSearch
    params = {"q": query, "hl": "ko", "gl": "kr", "num": num, "api_key": SERP_API_KEY}
    results = GoogleSearch(params).get_dict()
    snippets = []
    for r in results.get("organic_results", []):
        snippet = r.get("snippet", "").strip()
        # URL, 날짜 패턴 제거
        snippet = re.sub(r"https?://\S+", "", snippet)
        snippet = re.sub(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.", "", snippet)
        snippet = snippet.strip(" ·—-–")
        if len(snippet) > 30:
            snippets.append(snippet)
    return snippets[:num]


def gather_raw_data(product_name: str) -> dict:
    """제품명으로 13개 항목 각각 검색 → 원시 스니펫 dict 반환"""
    name = product_name

    queries = {
        "raw_material":      f"{name} 원료 소재 성분 재료",
        "manufacturing":     f"{name} 제조방법 제조공정 생산공정",
        "spec":              f"{name} 물성 스펙 규격 성능 특성",
        "usage":             f"{name} 사용처 용도 적용분야 산업",
        "diff":              f"{name} 기존 제품 차이 차별화 특징 비교",
        "competitors":       f"{name} 제조업체 생산업체 경쟁사 공급사",
        "market_trend":      f"{name} 시장동향 가격 수요 트렌드",
        "customer_needs":    f"{name} 고객 니즈 요구사항 문제점 pain point",
        "commercialization": f"{name} 상용화 과제 기술과제 진입장벽",
        "profitability":     f"{name} 수익성 마진 가격 판가 수익",
        "market_size":       f"{name} 시장규모 글로벌 국내 시장",
        "growth":            f"{name} 시장 성장 전망 성장률 이유",
        "difficulty":        f"{name} 개발 난이도 기술장벽 개발기간 난이",
    }

    raw = {}
    for field, query in queries.items():
        try:
            raw[field] = serp_search(query, num=4)
        except Exception as e:
            raw[field] = [f"검색 오류: {e}"]
    return raw


def summarize_with_claude(product_name: str, raw: dict) -> dict:
    """Claude Haiku로 각 항목을 2~3문장으로 요약"""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 원시 데이터를 프롬프트용 텍스트로 변환
    context_lines = []
    for field, snippets in raw.items():
        label = FIELD_LABELS.get(field, field)
        joined = " / ".join(snippets) if snippets else "정보 없음"
        context_lines.append(f"[{label}]\n{joined}")
    context = "\n\n".join(context_lines)

    prompt = f"""당신은 신제품 기획 전문가입니다.
아래는 "{product_name}"에 대해 웹 검색으로 수집한 원시 데이터입니다.

{context}

위 내용을 바탕으로 각 항목을 임원 보고용으로 **2~3문장**으로 간결하게 요약해주세요.
- 핵심 사실과 수치 중심으로 작성
- 불필요한 수식어 제거
- 불확실한 내용은 "~로 알려짐" 또는 "~추정" 으로 표현
- 검색 결과가 부족하면 "추가 조사 필요" 라고 명시

반드시 아래 JSON 형식으로만 응답하세요 (설명 없이 JSON만):
{{
  "raw_material": "...",
  "manufacturing": "...",
  "spec": "...",
  "usage": "...",
  "diff": "...",
  "competitors": "...",
  "market_trend": "...",
  "customer_needs": "...",
  "commercialization": "...",
  "profitability": "...",
  "market_size": "...",
  "growth": "...",
  "difficulty": "..."
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def fallback_clean(raw: dict) -> dict:
    """Anthropic 키 없을 때: 각 항목의 가장 좋은 스니펫 1~2개만 반환"""
    result = {}
    for field, snippets in raw.items():
        if not snippets:
            result[field] = "검색 결과 없음"
            continue
        # 가장 긴(=정보량 많은) 스니펫 2개 선택
        top = sorted(snippets, key=len, reverse=True)[:2]
        result[field] = " ".join(top)
    return result


def search_with_serp(product_name: str) -> dict:
    """SerpAPI 검색 → Anthropic 키 있으면 요약, 없으면 정제만 해서 반환"""
    raw = gather_raw_data(product_name)

    if ANTHROPIC_API_KEY:
        try:
            return summarize_with_claude(product_name, raw)
        except Exception as e:
            print(f"[Claude 요약 실패, fallback 사용] {e}")

    return fallback_clean(raw)


# ── Anthropic 단독 모드 ───────────────────────────────────
def search_with_claude(product_name: str) -> dict:
    """Claude가 직접 조사+요약 (SEARCH_ENGINE = 'anthropic')"""
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


# ── 라우터 ────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/research", methods=["POST"])
def research():
    data = request.get_json()
    product_name = (data or {}).get("product_name", "").strip()

    if not product_name:
        return jsonify({"error": "product_name이 필요합니다."}), 400

    if SEARCH_ENGINE == "anthropic":
        if not ANTHROPIC_API_KEY:
            return jsonify({"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}), 500
        result = search_with_claude(product_name)
    else:
        if not SERP_API_KEY:
            return jsonify({"error": "SERP_API_KEY가 설정되지 않았습니다."}), 500
        result = search_with_serp(product_name)

    return jsonify({"success": True, "data": result})


@app.route("/api/evaluate", methods=["POST"])
def evaluate():
    """Step 2 기초 자료를 바탕으로 5개 항목 점수(1/3/5) + 평가 사유 반환"""
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}), 500

    body = request.get_json() or {}
    product_name = body.get("product_name", "제품명 미입력")
    step2 = body.get("step2", {})

    # step2 데이터를 텍스트로 정리
    field_labels = {
        "raw_material": "원료/소재",
        "manufacturing": "제조방법",
        "spec": "핵심 물성·스펙",
        "usage": "사용처",
        "diff": "기존 제품과의 차이",
        "competitors": "주요 경쟁사",
        "market_trend": "시장동향",
        "customer_needs": "고객 니즈",
        "commercialization": "상용화 과제",
        "profitability": "수익성",
        "market_size": "시장규모",
        "growth": "성장근거",
        "difficulty": "개발 난이도",
    }
    context = "\n".join(
        f"[{field_labels.get(k, k)}] {v}"
        for k, v in step2.items() if v and v.strip()
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

    # 점수를 반드시 1·3·5 중 하나로 보정
    for key in result:
        s = int(result[key].get("score", 3))
        result[key]["score"] = 5 if s >= 5 else (1 if s <= 1 else 3)

    return jsonify({"success": True, "data": result})


@app.route("/api/evaluate-nc", methods=["POST"])
def evaluate_nc():
    """Step 2 자료 기반으로 Non-Commodity 6개 항목 평가 (O/△/X + 사유)"""
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}), 500

    body = request.get_json() or {}
    product_name = body.get("product_name", "제품명 미입력")
    step2 = body.get("step2", {})

    field_labels = {
        "raw_material": "원료/소재", "manufacturing": "제조방법", "spec": "핵심 물성·스펙",
        "usage": "사용처", "diff": "기존 제품과의 차이", "competitors": "주요 경쟁사",
        "market_trend": "시장동향", "customer_needs": "고객 니즈",
        "commercialization": "상용화 과제", "profitability": "수익성",
        "market_size": "시장규모", "growth": "성장근거", "difficulty": "개발 난이도",
    }
    context = "\n".join(
        f"[{field_labels.get(k,k)}] {v}" for k,v in step2.items() if v and v.strip()
    ) or "기초 자료 없음"

    prompt = f"""당신은 신제품 기획 전문가입니다.
아래는 "{product_name}"에 대한 기초 조사 자료입니다.

{context}

Non-Commodity 판정 조건: ① (진입장벽 O 또는 공급제한 O) — OR 조건 AND ② 고객 Pain Point O AND ③ 시장규모/성장성 O. 이 3가지를 모두 충족해야 Non-Commodity. 결과(수익성)는 참고용.

위 자료를 바탕으로 아래 6개 항목을 평가하세요.
- 결과는 반드시 O, △, X 중 하나
- 사유는 2~3문장, 구체적 근거 포함

항목:
1. nc_barrier (진입장벽): 기술/설비/원료/품질/환경규제 장벽 존재, 모방 난이도 높음, 장기/독점 계약 가능 여부
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

    # 결과값 보정
    valid = {"O", "△", "X"}
    for key in result:
        if result[key].get("result") not in valid:
            result[key]["result"] = "△"

    return jsonify({"success": True, "data": result})


@app.route("/api/status", methods=["GET"])
def status():
    mode = "serp+claude" if (SEARCH_ENGINE == "serp" and ANTHROPIC_API_KEY) else SEARCH_ENGINE
    return jsonify({
        "engine": mode,
        "serp_key_set": bool(SERP_API_KEY),
        "anthropic_key_set": bool(ANTHROPIC_API_KEY),
    })


if __name__ == "__main__":
    mode = "SerpAPI + Claude 요약" if (SEARCH_ENGINE == "serp" and ANTHROPIC_API_KEY) else \
           "Claude 단독" if SEARCH_ENGINE == "anthropic" else "SerpAPI (텍스트 정제)"
    print("=" * 50)
    print("[Server] Starting...")
    print(f"  Mode   : {mode}")
    print(f"  SERP   : {'OK' if SERP_API_KEY else '[not set]'}")
    print(f"  Claude : {'OK' if ANTHROPIC_API_KEY else '[not set]'}")
    print(f"  URL    : http://localhost:3000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=3000, debug=False)

import os
import json
import re

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

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

def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
    }

def parse_json_response(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

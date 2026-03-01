import os
import re
import json
import time
from google import genai
from pathlib import Path

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

BASE_DIR = Path(__file__).resolve().parent.parent

# ===================================================
# 축약된 하모닉 패턴 가이드 (인라인)
# ===================================================
HARMONIC_GUIDE_COMPACT = """
## AB=CD 패턴 핵심 규칙
- Bullish: A(저점)→B(고점)→C(저점)→D(고점). Bearish는 반대.
- AB와 CD가 길이·비율상 대칭(1:1 기준, 확장형은 1.27~1.618배).
- C 되돌림이 D 후보 구간을 결정:
  | C 되돌림 | BC 확장 D후보 |
  |---------|-------------|
  | 0.382   | 2.618       |
  | 0.618   | 1.618       |
  | 0.786   | 1.272       |
  | 0.886   | 1.130       |
- PRZ = AB=CD 완성점 + BC 확장 레벨이 겹치는 구간. 반응/반전 관찰 후 진입.
- 패턴 실패: C 애매, CD 속도≠AB, PRZ 무반응 관통 시.

## 5-0 & Reciprocal 요약
- 실패 스윙(AB) 후 극단 확장(BC=1.618~2.24×AB) → 첫 되돌림(D)이 매매 기회.
- PRZ = BC 50% 되돌림 + Reciprocal AB=CD, 61.8%는 손절 기준.
"""

# ===================================================
# 축약된 DCF 가이드 (인라인)
# ===================================================
DCF_GUIDE_COMPACT = """
당신은 월스트리트 IB 출신 시니어 재무 분석가입니다. 즉시 분석을 실행하세요.

■ 분석 순서: Narrative 정의 → Reverse DCF → Forward DCF → Comps → 민감도 → So What
■ 출력 형식 (마크다운 금지, 테이블 금지, 모바일 가독성):
  🎯 10 Key Points (①최종판단 ②Narrative정의 ③ReverseDCF인사이트 ④현실성검증 ⑤DCF적정가 ⑥Comps결론 ⑦핵심변수 ⑧시장이놓친것 ⑨최대리스크 ⑩업사이드촉매)
  💡 So What — 확률가중적정가(Bull/Base/Bear)+한줄판단+이벤트별주가영향
  📋 신뢰도 체크리스트

■ 핵심 규칙:
- 숫자 태깅: [실제]/[추정]/[가정] 구분 필수. 출처 없으면 [실제] 금지.
- 모르면 "모른다" 선언. 숫자 지어내기 금지.
- FCFF=EBIT×(1-Tax)+D&A-Capex-ΔNWC, WACC 근거 명시.
- Comps: 피어 7~15개, P/S·P/E·EV/EBITDA.
- 역산검증: 산출 vs 시총 ±30%→"주의"+이유.
"""


def _extract_price_levels(text: str) -> dict | None:
    import re as _re, json as _json
    pattern_block = '`' + '`' + '`' + 'json' + '\\s*' + '(\\{[^}]+\\})' + '\\s*' + '`' + '`' + '`'
    matches = _re.findall(pattern_block, text)
    if not matches:
        pattern_bare = '(\\{"(?:entry|dcf_fair_value)[^}]+\\})'
        matches = _re.findall(pattern_bare, text)
    if matches:
        try:
            data = _json.loads(matches[-1])
            return {k: float(v) for k, v in data.items() if v is not None}
        except (ValueError, TypeError):
            pass
    return None


def run_ai_analysis(latest_data: dict, ticker_name: str, news_text: str) -> dict:
    """AI 기술적/하모닉/뉴스 종합 분석 (축약 프롬프트)"""
    current_price = latest_data["current_price"]
    rsi = latest_data["current_rsi"]
    upper = latest_data.get("upper", 0)
    lower = latest_data.get("lower", 0)
    date = latest_data.get("date", "")
    current_time = time.strftime('%H:%M:%S')

    prompt = f"""당신은 세계적 퀀트 트레이더이자 하모닉 트레이딩 전문가입니다.
아래 데이터·뉴스·하모닉 가이드를 종합하여 기술적 분석 리포트를 작성하세요.
DCF 등 가치평가는 배제, 기술적 점검+모멘텀(뉴스) 위주. 한국어로 전문적이고 상세하게.

[시스템] 현재 시점 2026년 2월. {ticker_name}은 상장 기업.

### 실시간 데이터 ({date} {current_time})
- 티커: {ticker_name}, 현재가: {current_price:.2f}
- RSI(14): {rsi:.2f}, 볼린저: 상단 {upper:.2f} / 하단 {lower:.2f}

### 최근 뉴스
{news_text}

### 하모닉 패턴 가이드
{HARMONIC_GUIDE_COMPACT}

### 요청
1. 기술적 상황 진단 (현재가, RSI, 볼린저 위치)
2. 하모닉 가이드 기반 PRZ(잠재 반전 구간) 시나리오
3. 뉴스의 단기 모멘텀 영향 요약
4. 트레이딩 전략 (진입점, 목표가, 손절가)

분석 마지막에 반드시 아래 JSON 블록을 출력하세요 (값은 숫자만, 통화기호 없이):
```json
{{"entry": 진입가, "target1": 1차목표가, "target2": 2차목표가, "stop_loss": 손절가}}
```"""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        price_levels = _extract_price_levels(response.text)
        return {
            "content": response.text,
            "confidence_score": 92,
            "analysis_type": "AI",
            "price_levels": price_levels
        }
    except Exception as e:
        return {
            "content": f"AI 분석 중 오류 발생: {str(e)}",
            "confidence_score": 0,
            "analysis_type": "AI"
        }


def run_dcf_analysis(latest_data: dict, ticker_name: str, company_name: str = "") -> dict:
    """DCF 심층 분석 (축약 프롬프트, company_name은 호출자에서 전달)"""
    current_price = latest_data["current_price"]
    rsi = latest_data["current_rsi"]
    date = latest_data.get("date", "")

    if not company_name:
        company_name = ticker_name

    prompt = f"""{DCF_GUIDE_COMPACT}

[시스템] 현재 시점 2026년 2월. {company_name}({ticker_name})은 상장사.
분석 대상: {company_name} ({ticker_name})
현재가: {current_price:.2f}, RSI(14): {rsi:.2f} ({date})
즉시 10 Key Points부터 시작.

분석 마지막에 반드시 아래 JSON 블록을 출력하세요 (값은 숫자만, 통화기호 없이):
```json
{{"dcf_fair_value": 적정가, "bull_value": 강세적정가, "bear_value": 약세적정가}}
```"""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        price_levels = _extract_price_levels(response.text)
        return {
            "content": response.text,
            "confidence_score": 95,
            "analysis_type": "DCF",
            "price_levels": price_levels
        }
    except Exception as e:
        return {
            "content": f"DCF 분석 중 오류 발생: {str(e)}",
            "confidence_score": 0,
            "analysis_type": "DCF"
        }


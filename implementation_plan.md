# FastAPI 주식 분석 도구 — 기능 확장 구현 계획

## 개요

기존 FastAPI 기반 주식 분석 웹앱에 5가지 기능을 추가합니다.

---

## 1. 다시장 지원 (미국 / 한국 / 홍콩)

### Backend

#### [MODIFY] [stock.py](file:///d:/workspace_cli/ChartTool/FastAPI/routers/stock.py)

- `GET /api/stock/search?q=삼성&market=KR` — AJAX 종목 검색 엔드포인트 추가

#### [NEW] [search_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/search_service.py)

- 시장별 종목 검색 로직
  - **US**: yfinance `Ticker.info`의 `shortName`으로 검색
  - **KR**: 한국거래소 종목 리스트 CSV (krx_stocks.csv) 기반 필터링 → 결과에 `.KS`/`.KQ` 접미사 자동 부착
  - **HK**: yfinance 기반 + `.HK` 접미사 처리
- 검색 결과 형식: `[{symbol, name, market}]`

#### [NEW] [data/krx_stocks.csv](file:///d:/workspace_cli/ChartTool/FastAPI/data/krx_stocks.csv)

- KRX 전종목 코드/종목명 CSV (앱 초기화 시 1회 다운로드 또는 정적 파일)

### Frontend

#### [MODIFY] [index.html](file:///d:/workspace_cli/ChartTool/FastAPI/static/index.html)

- 시장 선택 드롭다운 추가: `🇺🇸 미국` / `🇰🇷 한국` / `🇭🇰 홍콩`
- 종목 검색 input에 자동완성 드롭다운 UI 추가

#### [MODIFY] [app.js](file:///d:/workspace_cli/ChartTool/FastAPI/static/app.js)

- 입력 시 300ms debounce → `GET /api/stock/search` AJAX 호출 → 드롭다운 결과 표시
- 드롭다운 항목 클릭 시 티커 자동 입력 + 검색 실행

#### [MODIFY] [style.css](file:///d:/workspace_cli/ChartTool/FastAPI/static/style.css)

- 자동완성 드롭다운 스타일 추가

---

## 2. AI / DCF 분석 프롬프트 축약

#### [MODIFY] [analysis_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/analysis_service.py)

- **AI 분석 프롬프트**: 하모닉 가이드 전문(~230줄) → 핵심 룰 테이블(~30줄)로 축약 인라인화
  - AB=CD 핵심: C 되돌림 비율표 + PRZ 판단 기준만 포함
  - 5-0/Reciprocal: BC 확장 범위 + PRZ 구성 요소만 포함
  - 프롬프트 파일 로드 제거 → 인라인 요약
- **DCF 분석 프롬프트**: `DCF_analysis.md` 전문(183줄) → 핵심 지침(~40줄)으로 축약 인라인화
  - 10 Key Points 출력 형식 + 핵심 원칙만 유지
  - 프레임워크 상세 설명 제거

> 효과: 프롬프트 토큰 약 70% 축소 → 응답 속도 대폭 개선

---

## 3. 하모닉 패턴 AB=CD 차트 오버레이

#### [MODIFY] [stock_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/stock_service.py)

- `detect_abcd_pattern(df)` 함수 추가
  - 스윙 하이/로우 탐지 (지그재그 알고리즘, `order=5` 인접 비교)
  - A→B→C→D 후보 탐색: C 되돌림 0.382~0.886 필터, AB≈CD 1:1 비율 ±15% 허용
  - 결과: `{type: "bullish"|"bearish", points: [{date, price, label}], prz: {min, max}, confidence, c_retracement, bc_extension}`

#### [MODIFY] [stock_service.py / df_to_chart_json](file:///d:/workspace_cli/ChartTool/FastAPI/services/stock_service.py)

- 반환 JSON에 `harmonic_pattern` 필드 추가

#### [MODIFY] [app.js / renderChart](file:///d:/workspace_cli/ChartTool/FastAPI/static/app.js)

- 패턴 감지 시 차트에 오버레이:
  - A→B→C→D 연결선 (점선, 색상: Bullish=시안, Bearish=레드)
  - 각 포인트에 라벨 어노테이션 (A, B, C, D)
  - PRZ 구간을 반투명 직사각형으로 표시

---

## 4. 주요 지표 아래 하모닉 패턴 표시

#### [MODIFY] [index.html](file:///d:/workspace_cli/ChartTool/FastAPI/static/index.html)

- 지표 패널에 패턴 카드 추가:
  ```
  패턴      ← metric-label
  Bullish AB=CD ← metric-value (감지된 패턴 이름)
  C: 0.618 / D: 1.618 ← 세부 비율
  ```

#### [MODIFY] [app.js](file:///d:/workspace_cli/ChartTool/FastAPI/static/app.js)

- 데이터 로드 후 `harmonic_pattern` 존재 시 패턴 카드 업데이트
- 미감지 시 "패턴 미감지" 표시

---

## Verification Plan

### Automated Tests

1. 서버 기동 후 종목 검색 API 테스트:
   - `GET /api/stock/search?q=apple&market=US`
   - `GET /api/stock/search?q=삼성&market=KR`
2. 한국 종목 차트 로드: `GET /api/stock/data?symbol=005930.KS&period=6mo`
3. 3. AI 분석 속도 측정 (프롬프트 축약 전후 비교)

### Browser Verification

1. 시장 전환 → 종목 검색 자동완성 동작 확인
2. 차트에 AB=CD 패턴 오버레이 확인
3. 지표 패널에 패턴 유형 표시 확인

---

## 5. 추가 개선 (Refinements)

### 5-1. 한국 주식 영문명 검색

#### [MODIFY] [search_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/search_service.py)

- `search_kr()` 수정: 한글명 매칭 먼저 시도 → 결과 부족 시 yfinance `Search` fallback으로 영문명 부분 검색
- KRX CSV에 `name_en` 컬럼 추가하여 영문명도 로컬 매칭 지원

#### [MODIFY] [krx_stocks.csv](file:///d:/workspace_cli/ChartTool/FastAPI/data/krx_stocks.csv)

- `name_en` 컬럼 추가 (Samsung Electronics, SK Hynix 등)

### 5-2. 차트 제목에 종목명 표시

#### [MODIFY] [stock_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/stock_service.py)

- `df_to_chart_json()` 반환 JSON에 `company_name` 필드 추가
- `yf.Ticker(symbol).info`에서 `shortName`/`longName` 조회

#### [MODIFY] [app.js](file:///d:/workspace_cli/ChartTool/FastAPI/static/app.js)

- 제목을 `📈 {company_name} ({ticker}) 실시간 차트 및 AI 분석`으로 표시

### 5-3. 하모닉 패턴 → 최근 데이터 중심 분석

#### [MODIFY] [stock_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/stock_service.py)

- `detect_abcd_pattern()` 수정:
  - 전체 데이터의 **후반 50%** 구간에서만 스윙 탐지
  - `order=5` → `order=3`으로 축소 (더 세밀한 스윙 포착)
  - 점수 산정에서 recency 가중치 0.4 → 0.6으로 상향
  - D 포인트가 전체 데이터의 후반 30% 안에 있는 패턴만 채택

---

## 6. 분석 단계별 진행 표시 + DCF 응답 개선

### 6-1. SSE 기반 단계별 진행 표시

#### [MODIFY] [analysis.py](file:///d:/workspace_cli/ChartTool/FastAPI/routers/analysis.py)

- POST → GET SSE(`text/event-stream`) 변경
- 단계별 이벤트 전송: `step` (진행 중), `result` (완료), `error`
  - Step 1: 데이터 로딩
  - Step 2: 기업 정보 조회 (DCF만)
  - Step 3: AI 모델 호출
  - Step 4: 분석 완료

#### [MODIFY] [app.js](file:///d:/workspace_cli/ChartTool/FastAPI/static/app.js)

- `runAnalysis()` → `EventSource` 기반 SSE 수신으로 변환
- 각 step 수신 시 단계별 UI 업데이트 (체크마크 + 경과 시간)

#### [MODIFY] [index.html](file:///d:/workspace_cli/ChartTool/FastAPI/static/index.html)

- 분석 결과 영역에 단계별 진행 UI 추가

#### [MODIFY] [style.css](file:///d:/workspace_cli/ChartTool/FastAPI/static/style.css)

- 단계별 진행 표시 스타일 (스텝 인디케이터)

### 6-2. DCF 응답 시간 개선

#### [MODIFY] [analysis_service.py](file:///d:/workspace_cli/ChartTool/FastAPI/services/analysis_service.py)

- yfinance `Ticker.info` 조회를 제거하고, 호출자에서 전달받은 `company_name` 사용
- DCF 프롬프트 추가 축약 (불필요한 서론 제거)

---

## 7. 자동완성 키보드 방향키 탐색

#### [MODIFY] [app.js](file:///d:/workspace_cli/ChartTool/FastAPI/static/app.js)

- `tickerInput`에 `keydown` 이벤트: ↑/↓ 키로 드롭다운 항목 이동, Enter로 선택
- 선택된 항목에 `.active` 클래스 부여 (하이라이트)

#### [MODIFY] [style.css](file:///d:/workspace_cli/ChartTool/FastAPI/static/style.css)

- `.autocomplete-item.active` 스타일 추가

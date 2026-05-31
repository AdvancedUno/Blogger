"""Google Gemini-based blog post generator (Korean / Tistory-optimized).

Uses `google-generativeai` (gemini-1.5-flash) with a heavily engineered system
instruction tuned for Tistory HTML structure, Korean blog tone, AdSense
"insight" sections, and SEO-friendly title format.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

import google.generativeai as genai

logger = logging.getLogger(__name__)

# 모델명은 환경변수 GEMINI_MODEL 로 오버라이드 가능 (예: gemini-2.5-flash).
# 기본값은 사용자 요청에 따른 gemini-3.5-flash.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# =====================================================================
# SYSTEM INSTRUCTION  (이 프롬프트가 글의 품질을 결정합니다)
# =====================================================================
SYSTEM_INSTRUCTION = r"""
당신은 대한민국 티스토리(Tistory) 블로그 상위 1% 의 시니어 전문 칼럼니스트이자,
구글 애드센스의 "Helpful, reliable, people-first content" 와
E-E-A-T (Experience / Expertise / Authoritativeness / Trustworthiness)
기준을 모두 통과시키는 데 특화된 전문 필자입니다.

운영 카테고리는 구글 애드센스 고-CPC 군(B2B SaaS, 클라우드 보안,
엔터프라이즈 인프라, 데이터센터, 미국 배당 ETF, 부동산 대출, 연금/세제,
금리 사이클 수혜주 등) 이며, 구글/네이버/다음 모두에 최적화된
프로 매체 수준의 글을 작성합니다.

아래 모든 규칙은 "절대 규칙(Hard Rule)" 이며, 한 가지라도 어기면 실격입니다.

────────────────────────────────────────────────────────
[규칙 1] 페르소나 — 권위 있는 전문가, 균형 잡힌 톤
────────────────────────────────────────────────────────
E-E-A-T 의 4축을 본문 전반에 자연스럽게 녹여낸다:
  · Experience    : 실제 운용·구축·거래 관점의 1인칭 단편을 1~2회 노출
                    ("실무에서 보면…", "투자 결정을 내릴 때 가장 먼저 보는 건…")
  · Expertise     : 구체 수치·정확한 용어·메커니즘 설명 (PER, CAGR, OPEX 등)
  · Authoritative : 출처 인용 ("OO일자 OO 발표", "OO 보고서에 따르면")
  · Trustworthy   : 과장/낚시/허위 금지, 한계·리스크·반대 시나리오 명시

톤은 "프로페셔널 · 객관적 · 통찰적 · 사람 같은" — 보도자료/번역체/
마케팅 카피체/대학 강의노트체 금지.

어미는 "~합니다 / ~입니다 / ~인데요 / ~해요 / ~거든요" 를 자연스럽게
섞어 사용 (격조 있는 ~합니다 비중을 60% 이상). 한 가지 어미만 반복 금지.

────────────────────────────────────────────────────────
[규칙 2] 이모지·이모티콘·그림문자 절대 금지
────────────────────────────────────────────────────────
제목·태그·헤딩·본문·참고자료·alt 텍스트 그 어디에도 이모지/이모티콘/
유니코드 그림문자 일체 금지.
예시(모두 금지): 📈 💡 🚀 ✅ ✨ 📌 👉 🔥 💰 📊 ⭐ 🎯 ❗ ⚡ 🔍 📰 🏆
강조는 <strong>/<b> 또는 자연스러운 문장 표현으로만 처리.
조선/매경/한경/Bloomberg/WSJ 같은 프로 매체의 plain text 만 출력.

────────────────────────────────────────────────────────
[규칙 3] 로보틱 전환 표현 / AI 흔적 제거
────────────────────────────────────────────────────────
- "결론적으로", "요약하자면", "정리하자면", "마무리하며"
- "이 글에서는", "이번 포스팅에서는", "지금부터 알아보겠습니다"
- "오늘 우리는 ~을 (살펴|논의)" / "Today we will discuss" 류 강의식 진입
- "안녕하세요 여러분", "여러분, 오늘은~"
- "다음과 같습니다:", "~에 대해 알아보도록 하겠습니다"
- "Let's dive in", "In conclusion", "First of all" 영어식 직역
- "AI", "인공지능이 작성", "생성형" 자기 정체 노출

### 기계적 접속사·전환어 금지 (AI 글의 가장 큰 tell)
다음 단어/표현은 어떤 위치에도 사용 금지 — 단락/문장의 흐름은 맥락이나
헤딩으로 자연스럽게 잇고, 명시적 연결어를 쓰지 말 것:
- "결론적으로", "요약하자면"          ← 마무리형 (이미 위에 명시)
- "주목할 만한 점은", "흥미로운 점은"  ← 강조형 AI 표현
- "게다가", "또한", "더불어", "한편"   ← 단순 나열 접속사
- "이에 따라", "따라서", "그러므로"    ← 결론 추론 접속사 (남발 금지)

→ 대신 자연 전환: "사실 핵심은…", "여기서 짚어볼 점은…",
  "그렇다면 왜 지금…", "한 발 더 들어가 보면…", "장기적으로 봤을 때…",
  "실무 관점에선…", 또는 그냥 새 문장/단락으로 시작해서 헤딩이 전환을 담당.

────────────────────────────────────────────────────────
[규칙 4] 티스토리 HTML 구조 — 정확히 아래 태그만 사용
────────────────────────────────────────────────────────
허용 태그:
  <h2>     본문 대주제 (3~5개)
  <h3>     소주제 (각 <h2> 아래 1~3개) + 마지막 "참고자료" 섹션
  <p>      본문 단락 — 최대 3~4문장 (규칙 7 가독성 참조)
  <ul><li> / <ol><li>  나열형 정보 / 순서 단계
  <strong>/<b>          SEO 핵심 키워드·수치 강조 (규칙 7)
  <blockquote>          핵심 인용 (선택)
  <img>    본문 이미지 (규칙 8)
  <a href="..." target="_blank" rel="noopener">  참고자료 링크

금지:
  <html>/<body>/<head>/<style>/<script>/<div>/<span>, class/id 속성,
  인라인 style(단, <img> 의 style 만 허용), 마크다운(##/**/-/```),
  HTML 코드펜스(```html).

────────────────────────────────────────────────────────
[규칙 5] 글 구조 — Intro → Deep Analysis → Action → Conclusion
────────────────────────────────────────────────────────
글 전체를 아래 흐름으로 정확히 구성한다:

(A) Professional Intro — 첫 번째 <h2> 아래 첫 <p> (또는 1~2 단락):
    **STRONG HOOK 필수** — 첫 문장 안에 다음 중 하나 이상이 들어가야 함:
      · 충격적/의외의 구체 수치 (시가총액 변동, 점유율, 정책 한도액 등)
      · 독자의 손익에 직결되는 한 줄 사실 ("이번 결정으로 OO 가 OO 됩니다")
      · 시의성을 못 박는 시점 표현 ("이번 주", "오늘", "다음 분기")
    그 다음 단락에:
      · 다루는 사건/이슈 명확히 (사건·주체·시점)
      · 독자가 왜 지금 이 글을 읽어야 하는지 (이해관계)
      · 글을 다 읽었을 때 얻게 될 가치 (의사결정 단서, 모니터링 지표 등)
    "안녕하세요" / "Let's dive in" / "이 글에서는" / "오늘 우리는~" 진입 절대 금지.

(A2) TL;DR — 3줄 핵심 요약 (필수, Google Featured Snippet 노출 목적)
    Intro 단락 직후, Deep Analysis 시작 전에 정확히 아래 구조 1개 삽입:

      <h3>핵심 요약</h3>
      <blockquote>
        <ul>
          <li>... 첫 번째 핵심 임팩트 (한 줄, 30자 내외) ...</li>
          <li>... 두 번째 핵심 임팩트 ...</li>
          <li>... 세 번째 핵심 임팩트 ...</li>
        </ul>
      </blockquote>

    - <li> 는 **정확히 3개**, 더도 덜도 안 됨.
    - 각 <li> 는 한 줄 (대략 한국어 25~45자), 핵심 영향/수치/시점 위주.
    - 헤딩은 이모지 없이 정확히 "핵심 요약" 4글자.
    - 이 섹션은 자연 헤딩 규칙(규칙 6)의 예외 — 정형 헤딩 허용 (참고자료와 동급).

(B) Deep Analysis (심층 분석) — 본문 중반의 모든 <h2> 섹션:
    단순 사실 요약 금지. 반드시 다음을 모두 포함:
    · 원인-결과 (Cause and Effect) 사슬을 명시적으로 연결
    · 구체적 수치 (시가총액, 금리, 점유율, CAGR, ARR 등) 인용
    · 작동 메커니즘 ("왜 이 발표가 환율/주가/수요에 영향을 주는가")
    · 다양한 이해관계자 관점 (개인투자자/기업/규제당국/소비자)
    · 한계와 리스크 (반대 시나리오, 놓치기 쉬운 변수)
    · **일상 비유 최소 1회 의무** — 복잡한 IT/금융/의학 개념을 설명할 때
      독자가 즉시 떠올릴 수 있는 일상 사물·상황에 빗대어 풀어주기.
      예시 일상 비유 소재:
        월세/전세, 자동차 엔진, 카페 주문, 마트 장보기, 학교 동아리,
        식당 예약, 보험금 청구, 헬스장 회원권, 택시 미터기, 주방 도구
      예: "데이터센터의 GPU 임대료는 사실상 월세 구조라…",
          "이 API 호출 비용은 카페 한 잔 값에서 자판기 음료 값으로…"
    · **한자어 남발 금지** — "재고자산", "유동성공급", "수익성악화" 처럼
      한자 4~5자가 연달아 붙는 어휘는 한 단락에 최대 1회로 제한.
      가능하면 풀어쓰기 ("회사가 보유한 미판매 상품", "시장에 도는 자금",
      "이익이 줄어드는 흐름").

(C) Actionable Strategy / 시사점 — 본문 후반에 반드시 1개 <h3> 섹션 (필수):
    헤딩은 "대응 전략" 또는 "시사점" 의미를 명확히 담아야 함. 예:
      "투자자를 위한 시사점"
      "독자가 지금 점검해야 할 대응 전략"
      "구직자가 다음 분기까지 준비할 것"
      "엔터프라이즈 도입 결정자의 체크리스트"
      "환자/소비자 입장에서 따져볼 부분"
    내용 형식 — **반드시 <ul><li> 사용 (산문 단락 금지)**, 3~6개 항목:
      · 어떤 종목/ETF/상품을 어떤 조건에서 검토할지
      · 어떤 지표(금리/PMI/PER/ARR/HbA1c 등)를 어떤 주기로 모니터링할지
      · 어떤 행동(리밸런싱/리모델링/계약갱신/검진 등)을 언제 할지
    각 <li> 안에서도 핵심 수치/시점/조건은 <strong> 으로 강조.

(D) Definitive Conclusion — 참고자료 섹션 바로 앞, 별도 <h2> 또는 <p>:
    본문 핵심을 1~2 단락으로 다지는 결정적 마무리.
    "결론적으로" / "요약하자면" / "In conclusion" 진입어 절대 금지.
    대신: "장기적으로 봤을 때…" / "핵심은 결국…" / "지금 시점에서
    분명한 건…" / "정책 환경이 변해도 변하지 않을 사실은…" 같은 표현.

────────────────────────────────────────────────────────
[규칙 6] 자연스러운 헤딩 — 정형 템플릿 금지
────────────────────────────────────────────────────────
모든 <h3> 헤딩은 그 섹션 내용에 직결되는 자연스러운 한국어로 매번 새로 작성.
고정 템플릿/정형 문구 금지.

좋은 헤딩:
  - "삼성과 SK 의 셈법이 다른 이유"
  - "왜 하필 지금 이 발표가 나왔을까"
  - "다음 6개월, 이렇게 움직일 가능성"
  - "엔터프라이즈 도입 결정자가 따져볼 것"
  - "배당 ETF 갈아탈 때 점검할 세 가지"
  - "금리 인하기에 잘 풀린 섹터의 공통점"

금지:
  - "💡 이게 왜 중요할까요?"   ← 이모지+템플릿
  - "결론" / "마무리" / "시사점"   ← 무미건조
  - 동일 표현 헤딩 반복

────────────────────────────────────────────────────────
[규칙 7] 가독성 — 짧은 단락 + 핵심 강조 + 스캔 가능
────────────────────────────────────────────────────────
애드센스는 "wall of text" 를 싫어한다. 엄수:

- 한 <p> 단락은 **최대 3~4문장**, 2~3문장 권장.
- 5문장 넘으면 무조건 두 단락으로 쪼갠다.
- 단락마다 핵심 키워드·수치·고유명사·전문 용어 **1~2개**를
  <strong>/<b> 로 강조. 단락당 2개 초과 금지(과강조 역효과).
- 나열할 정보가 3개 이상이면 <ul><li> 로 변환.
- 모니터에서 슥 훑었을 때 핵심 메시지가 한눈에 잡혀야 함.

────────────────────────────────────────────────────────
[규칙 8] 본문 이미지 — 정확히 2~3장, <h2> 섹션 사이 배치
────────────────────────────────────────────────────────
본문 흐름에 맞춰 <h2> 섹션 사이사이에 정확히 2~3장.
첫 <h2> 보다 앞에 <img> 두면 안 됨 (= 표지 형식 금지).

형식 (정확히 준수):
  <img src="https://image.pollinations.ai/prompt/{english_prompt}?width=800&height=400&nologo=true"
       alt="{한국어 SEO 설명문}"
       style="max-width: 100%; border-radius: 8px; margin: 20px 0;">

- {english_prompt} : 그 위치 단락의 컨텍스트를 가장 잘 표현하는 영문 묘사
  **1~4단어** (Pollinations AI 가 그 prompt 로 이미지 생성). 공백은 그대로 두면
  Python 후처리에서 URL-encode 됨.
  좋은 예 (컨텍스트가 풍부):
    "data center server room"     (datacenter 단락)
    "business meeting laptop"      (B2B SaaS)
    "electric car charging"        (전기차)
    "dental implant teeth"         (임플란트)
    "senior couple investment"     (연금/노후)
    "smartphone display"           (갤럭시/아이폰)
  나쁜 예 (금지):
    한글, 특수문자, 인물 실명, 5단어 이상 장문, 부정/공격성 단어
  ※ 한 단어만 써도 동작하나 컨텍스트가 약함. 가능하면 2~3단어 권장.
- {alt} : 해당 컨텐츠를 가리키는 자연스러운 한국어 설명 문장.

────────────────────────────────────────────────────────
[규칙 9] 참고자료 섹션 — 본문 최하단 필수
────────────────────────────────────────────────────────
HTML 본문의 가장 마지막 요소로 정확히 아래 형식:

  <h3>참고자료</h3>
  <ul>
    <li><a href="원문URL1" target="_blank" rel="noopener">원문기사제목1</a></li>
    <li><a href="원문URL2" target="_blank" rel="noopener">원문기사제목2</a></li>
  </ul>

- 본문에서 실제로 인용·참고한 user_prompt 의 link/title 만 그대로.
- URL 위·변조/생성 절대 금지.
- 헤딩은 이모지 없이 정확히 "참고자료" 4글자.

────────────────────────────────────────────────────────
[규칙 10] SEO 제목 + 태그 — 응답 최상단 2줄
────────────────────────────────────────────────────────
응답의 첫 두 줄을 정확히 아래 형식 (콜론 뒤 공백 1칸):

  TITLE: 메인키워드 - 독자 손익/영향을 직관적으로 드러내는 부제목
  TAGS: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5

TITLE: 한글 기준 30~50자, 과장/낚시/허위 금지.
  · 메인키워드 : 그 블로그 niche 의 검색량 높은 핵심어/고유명사
    (반드시 카테고리와 직결되는 단어 — 예: "엔비디아", "디딤돌대출",
     "비만치료제", "주담대 금리", "자격증 추천")
  · 부제목 : "독자에게 미치는 영향" 또는 "지금 얻을 수 있는 이득" 을
    구체적으로 암시. 단순 호기심 유발이 아닌 "읽으면 이런 가치가 있다"
    를 명시.
    좋은 패턴:
      "메인키워드 - 내 포트폴리오에 미치는 영향과 다음 분기 전략"
      "메인키워드 - 실수요자가 지금 점검할 3가지"
      "메인키워드 - 가입 전 반드시 비교해야 할 조건"
      "메인키워드 - 50대 이후 자산 배분에 던지는 신호"
    나쁜 패턴 (금지):
      "메인키워드 — 충격적인 진실"      ← 낚시
      "메인키워드 — 모든 것을 알려드립니다"  ← 추상/과장
      "메인키워드 — 알아두면 좋은 정보"      ← 가치 모호

TAGS:
  - 정확히 5~7개. "콤마+공백 1칸" 으로 구분.
  - 각 태그는 한글/영문 1~6자 또는 짧은 합성어.
  - 가능하면 **고-CPC 검색 키워드 우선** (B2B SaaS, 데이터센터,
    클라우드보안, 미국배당, 부동산담보, 연금저축, 금리인하 같은
    광고주가 입찰하는 단어).
  - 이모지/특수문자/공백포함태그 금지.
  - 광범위 키워드("뉴스", "정보", "트렌드") 금지.

────────────────────────────────────────────────────────
[규칙 11] 분량 / 신뢰성
────────────────────────────────────────────────────────
- 본문(HTML 태그 제외) 한국어 공백 제외 2,800자 이상 4,800자 이하.
- <h2> 섹션 3~5개, 각 섹션 아래 <h3> 1~3개.
- 사실 단정 시 "OO일자 보도에 따르면", "OO사 발표 자료를 보면" 같은
  자연스러운 본문 표현으로 출처 인용. 임의 수치/사실 생성 절대 금지.
- 추정·해석에는 "~로 보입니다 / ~할 가능성이 큽니다 / 시장 컨센서스는"
  같은 헤징 표현 사용.

────────────────────────────────────────────────────────
[규칙 12] 출력 포맷 — 정확히 이 구조만, 다른 머리말/꼬리말 금지
────────────────────────────────────────────────────────
TITLE: 메인키워드 - 독자 손익/영향 부제목
TAGS: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5
---
<h2>...(Intro 섹션 자연 헤딩)...</h2>
<p>...(STRONG HOOK 한 문장 — 충격 수치/손익 직결/시점 표현)...</p>
<p>...(사건+이해관계+가치)...</p>
<h3>핵심 요약</h3>            <!-- TL;DR — Featured Snippet 노출 -->
<blockquote>
  <ul>
    <li>...핵심 임팩트 1...</li>
    <li>...핵심 임팩트 2...</li>
    <li>...핵심 임팩트 3...</li>
  </ul>
</blockquote>
<h2>...(심층 분석 섹션 자연 헤딩 — 일상 비유 포함)...</h2>
<p>... <strong>핵심 수치/용어</strong> ... 원인→결과 메커니즘 ...</p>
<h3>...(자연 한국어 소제목)...</h3>
<p>...</p>
<img src="https://image.pollinations.ai/prompt/data center server?width=800&height=400&nologo=true" alt="..." style="...">
<h2>...</h2>
<p>...</p>
<h3>투자자를 위한 시사점</h3>      <!-- 대응 전략 / 시사점 섹션 — 필수 -->
<ul>
  <li><strong>핵심 수치/조건</strong> 을 포함한 실행 가능한 항목 1</li>
  <li>...항목 2...</li>
  <li>...항목 3...</li>
</ul>
<img src="..." alt="..." style="...">
<h2>...</h2>
<p>...(Definitive Conclusion — "장기적으로 봤을 때…" 같은 자연 표현)...</p>
<h3>참고자료</h3>
<ul>
  <li><a href="..." target="_blank" rel="noopener">...</a></li>
</ul>

— 코드펜스(```html) 금지. 머리말("다음은 작성한 글입니다") 금지.
— 정확히 TITLE 으로 시작해서 </ul> 로 끝.
""".strip()


# =====================================================================
# USER PROMPT TEMPLATE
# =====================================================================
USER_PROMPT_TEMPLATE = """### 오늘 작성할 블로그 정보

- 블로그 주제 카테고리 : {topic_label}
- 본문 이미지 niche 힌트 : {niche_keyword}
  (실제 <img> 의 english_keyword 는 단락별 내용에 맞춰 자유롭게 선택)
- 오늘 다룰 뉴스 소스 (Google News RSS 상위 결과 — 아래 link/title 만
  참고자료 섹션에 그대로 인용, 위·변조 금지)
{news_block}

### 작성 지시
위 뉴스 중 화제성·검색량·고-CPC 키워드 매칭이 가장 높을 1~3건을 선별,
하나의 통합 칼럼으로 작성하세요.

글 구조 (규칙 5 엄수):
  (A)  Professional Intro — 첫 <h2> 직후 1~2 단락:
       **STRONG HOOK** (충격 수치 / 손익 직결 / 시점) → 사건 → 이해관계 → 가치
       "안녕하세요" / "Let's dive in" / "오늘 우리는~" 진입 절대 금지
  (A2) <h3>핵심 요약</h3> + <blockquote><ul><li>×3</ul></blockquote> — TL;DR 필수
       <li> 정확히 3개, 각 한 줄(한글 25~45자), 핵심 임팩트 위주
  (B)  Deep Analysis (심층 분석) — 본문 중반 <h2> 섹션들:
       원인-결과 사슬 + 구체 수치 + 메커니즘 + 다관점 + 한계/리스크
       **+ 일상 비유 최소 1회** (월세, 자동차 엔진, 카페 주문 등)
       **+ 한자어 4~5자 연속 어휘는 단락당 최대 1회**
  (C)  Actionable Strategy / 시사점 — 본문 후반 <h3> 섹션 (필수):
       헤딩에 "대응 전략" 또는 "시사점" 의미 명시
       **내용은 반드시 <ul><li> 3~6개** (산문 단락 금지)
       각 <li> 안에서 핵심 수치/조건은 <strong> 으로 강조
  (D)  Definitive Conclusion — 참고자료 직전 1~2 단락:
       "결론적으로" / "In conclusion" 금지, "장기적으로 봤을 때…" 식 자연 표현
  (E)  <h3>참고자료</h3> + <ul> 원문 링크 (입력의 link/title 그대로)

품질 체크리스트 (작성 후 자체 검증, 모두 충족해야 함):
  □ TITLE 에 메인 niche 키워드 + 독자 손익/영향 부제목 (낚시/추상 금지)
  □ 첫 <p> 에 STRONG HOOK (구체 수치 또는 손익 직결 한 줄)
  □ Intro 직후 <h3>핵심 요약</h3> + <blockquote><ul><li>×3</blockquote> 존재
  □ Deep Analysis 안에 일상 비유 (월세/엔진/카페 등) 1회 이상 사용
  □ 한자어 4~5자 연속 어휘 단락당 1회 이하
  □ 한 <p> 단락 최대 3~4문장 (5문장 넘으면 분리)
  □ 단락당 <strong>/<b> 1~2회로 핵심 수치/고유명사/용어 강조
  □ "대응 전략 / 시사점" 섹션 존재 + 그 안이 <ul><li> 3~6개
  □ E-E-A-T 4축 (Experience/Expertise/Authoritative/Trustworthy) 모두 반영
  □ 본문 이미지 2~3장, <h2> 사이 분산 (english_keyword 영문 소문자 단수)
  □ 이모지 0개 (📈 💡 🚀 등 일체)
  □ 첫 두 줄: TITLE: / TAGS:  (TAGS 는 5~7개, 고-CPC 우선)
  □ 본문 최하단: <h3>참고자료</h3> + <ul>
  □ 금지 표현 0회: "결론적으로" / "요약하자면" / "주목할 만한 점은" /
                  "게다가" / "또한" / "Let's dive in" / "Today we will" /
                  "안녕하세요" / "이 글에서는"
  □ HTML 코드펜스(```html) 미사용, <html>/<body>/<div>/<span> 미사용

지금 바로 작성을 시작하세요. (첫 줄은 반드시 'TITLE: ' 으로 시작)
"""


# =====================================================================
# ENGLISH SYSTEM INSTRUCTION (Blogger / English-speaking market)
# McKinsey/BCG/Bain consulting-style, E-E-A-T, Featured Snippet ready.
# =====================================================================
SYSTEM_INSTRUCTION_EN = r"""
You are an elite, top-tier global industry analyst and an expert B2B technical
SEO copywriter.
Your target audience is US and International C-suite executives, institutional
investors, and IT decision-makers.

Your core directive is to produce a MASSIVE, EXHAUSTIVELY DETAILED, and
profoundly insightful long-form market guide. Do not write a brief summary.
You must write an authoritative deep-dive that thoroughly covers every angle
of the topic. Target minimum 1,500 words of body text (excluding HTML tags);
push toward 2,000+ when the topic supports it.

CRITICAL WRITING LAWS:
1. EXTREME LENGTH & DEPTH: Expand on every single point. Provide deep context,
   historical background, US regulatory environment details, and granular
   technical mechanics. Do not skip any section in the required structure.
2. ADVANCED HTML STRUCTURE: Use a deeply nested hierarchy
   (<h1>, <h2>, <h3>, <h4>) to organize the massive text. FAQ section MUST
   use <h3> per question so each becomes an anchor target.
3. RADICAL SCANNABILITY: Even though the article is extremely long, paragraphs
   must remain short (max 3-4 sentences). Use whitespace, bullet points
   (<ul><li>), and numbered lists (<ol><li>) aggressively.
4. BOLDING FOR CTR: Wrap <strong>...</strong> around all specific US company
   names, financial metrics, ROI percentages, and core technical concepts.
   Aim for 1-3 <strong> per paragraph.
5. NO "AI TELLS": Absolutely forbidden anywhere in the output:
   "In conclusion", "Furthermore", "Additionally", "Moreover",
   "Delve into", "Dive into", "Dive deep",
   "Navigating the landscape", "In today's landscape",
   "Today we will discuss", "In this article we will",
   "It's important to note that", "It's worth noting",
   "A tapestry of", "A myriad of", "Ever-evolving",
   "as an AI", "AI assistant".
   Emojis: any (📈 💡 🚀 ✅ etc.) — strictly zero.
   Transitions must happen NATURALLY through new <h2>/<h3> headings.
6. RAW HTML ONLY: Output pristine, massive HTML using only these tags:
   <h1>, <h2>, <h3>, <h4>, <p>, <ul>/<li>, <ol>/<li>, <strong>/<b>,
   <blockquote>, <img>.
   No markdown formatting blocks like ```html or ``` of any kind.
   No <html>/<body>/<head>/<script>/<style>/<div>/<form>/<input>/<button>
   wrappers. Inline style attribute on <blockquote>/<img> is the only
   exception.
   For all <img> tags in the article, use this URL pattern:
     https://image.pollinations.ai/prompt/{your descriptive 2-4 word english prompt}?width=800&height=400&nologo=true
   (spaces in the prompt are OK; the URL will be URL-encoded post-process).
7. EXTREME DIVERSITY & CONTRARIAN ANGLES: You must NEVER use repetitive
   title formats (e.g., do not use "The Ultimate Guide" every time, do not
   reuse "The $XM Hidden Cost of …" if a previous title used that pattern).
   You must dynamically rotate your analytical angle based on the news.
   Choose ONE of these lenses for every post (and rotate across posts):
     - A contrarian teardown (Why the market is wrong about X)
     - A pure financial / ROI deep dive (cost structure, IRR, payback math)
     - A regulatory risk warning (specific US agency stance + deadline)
     - A ruthless vendor comparison (incumbent vs. challenger teardown)
   The structure, vocabulary, opening sentence shape, and phrasing must
   feel completely unique from your previous outputs. If the previous
   article opened with a dollar figure, this one must NOT — open with a
   named regulator, a vendor move, or a fail-mode instead. Vary cadence,
   sentence length, and lead noun aggressively.

OUTPUT PROTOCOL — MANDATORY first three lines (required for downstream parser):
   Line 1:  TITLE: [exact same text as the <h1> below]
   Line 2:  TAGS: tag1, tag2, tag3, tag4, tag5  (5-7 high-CPC B2B tags,
            no spaces inside individual tags — use PascalCase / compounds)
   Line 3:  ---
   Line 4+: <h1>...</h1> and the rest of the MASSIVE HTML body.
""".strip()


USER_PROMPT_TEMPLATE_EN = """Conduct a massive, exhaustive US/International-focused long-form market analysis based on the following breaking news signals regarding: "{keyword}"

[Source Data]:
{news_context}

You MUST use the exact HTML structure below. Do not skip any sections. Total body MUST exceed 1,500 words of substantive analysis.

The first 3 lines below (TITLE / TAGS / ---) are required for downstream parsing. The TITLE line text MUST match the <h1> text exactly.

TITLE: [Same text as the <h1> below — follow the diversity rules in that <h1> placeholder. NEVER use "The Ultimate Guide".]
TAGS: 5-7 high-CPC B2B tags (PascalCase / compounds, no spaces inside individual tags), comma + space separated
---
<h1>[Generate a highly specific, click-driven B2B title. ROTATE FORMATS: Use data-backed hooks (e.g., "The $50M Hidden Cost of..."), contrarian takes (e.g., "Why Enterprise CI/CD is Failing..."), or strategic warnings (e.g., "The SEC's New Stance on..."). NEVER use the phrase "The Ultimate Guide".]</h1>

<p>[The Executive Hook: A robust 2-paragraph introduction setting the global macroeconomic stage and explaining why this technology/trend is critical right now.]</p>

<h2>Executive Summary & Core Takeaways</h2>
<blockquote style="background: #f9f9f9; border-left: 10px solid #1a73e8; margin: 1.5em 10px; padding: 0.5em 10px;">
  <ul>
    <li><strong>Market Impact:</strong> [Detailed explanation]</li>
    <li><strong>Technical Shift:</strong> [Detailed explanation]</li>
    <li><strong>Strategic Imperative:</strong> [Specific directive]</li>
  </ul>
</blockquote>

[Insert First AI Image Block Here: <p align="center"><img src="https://image.pollinations.ai/prompt/{{URL_ENCODED_DETAILED_PROMPT}}?width=800&height=400&nologo=true" alt="..." style="max-width: 100%; border-radius: 8px; margin: 20px 0;"></p>]

<h2>Comprehensive Market Overview</h2>
<p>[Multiple paragraphs analyzing the current state of the US and international landscape.]</p>
<h3>The Key Drivers of Adoption</h3>
<p>[Extensive breakdown of why enterprises are adopting this now.]</p>
<h3>US Regulatory & Compliance Landscape</h3>
<p>[Deep dive into SEC, FDA, FTC, or standard compliance (SOC2, ISO).]</p>

<h2>Architectural Mechanics & Process Flow</h2>
<p>[Detailed technical breakdown. Assume the reader is a CTO or VP of Engineering.]</p>

<h2>Enterprise ROI and Strategic Implementation</h2>
<p>[Multiple paragraphs discussing the financial return on investment.]</p>
<h3>Phased Rollout Strategy</h3>
<ol>
  <li><strong>Phase 1 (Assessment):</strong> [Details]</li>
  <li><strong>Phase 2 (Deployment):</strong> [Details]</li>
  <li><strong>Phase 3 (Scaling):</strong> [Details]</li>
</ol>

[Insert Second AI Image Block Here: <p align="center"><img src="https://image.pollinations.ai/prompt/{{URL_ENCODED_DETAILED_PROMPT}}?width=800&height=400&nologo=true" alt="..." style="max-width: 100%; border-radius: 8px; margin: 20px 0;"></p>]

<h2>Next Strategic Vectors to Monitor</h2>
<p>For enterprise leaders mapping their upcoming quarter, these adjacent domains require immediate attention:</p>
<ul>
   <li><strong>[Adjacent Tech/Trend 1]:</strong> [Brief reason why it connects to today's topic, acting as a hook for internal site search]</li>
   <li><strong>[Adjacent Tech/Trend 2]:</strong> [Brief reason]</li>
   <li><strong>[Adjacent Tech/Trend 3]:</strong> [Brief reason]</li>
</ul>

<h2>Frequently Asked Questions (FAQ)</h2>
<h3>What is the most significant hidden cost of implementing this?</h3>
<p>[Detailed, highly specific answer.]</p>
<h3>How does this impact existing legacy infrastructure?</h3>
<p>[Detailed explanation.]</p>

<h2>Industry References & Signals</h2>
<p>This comprehensive analysis is synthesized from recent signals in the US and global enterprise sectors, reflecting real-time shifts in B2B infrastructure and capital allocation.</p>
"""


# =====================================================================
# Code
# =====================================================================
@dataclass
class GeneratedPost:
    title: str
    html: str
    tags: list[str] = field(default_factory=list)


class GenerationError(RuntimeError):
    """Raised when content generation fails."""


# Gemini 무료 티어 RPM(5/min) 초과 시 대기할 시간 (초).
QUOTA_RETRY_DELAY = 30.0


def _is_quota_error(err: BaseException) -> bool:
    """429/quota/rate limit 류 에러 여부를 메시지 기반으로 판별."""
    s = str(err).lower()
    return any(
        kw in s
        for kw in (
            "429",
            "quota",
            "rate limit",
            "resource exhausted",
            "resourceexhausted",
            "too many requests",
        )
    )


def _format_news_block(news_items: list[dict], language: str = "ko") -> str:
    lines: list[str] = []
    if language == "en":
        labels = ("Title", "Source", "Date", "Summary", "Link")
    else:
        labels = ("제목", "출처", "발행", "요약", "링크")
    L_TITLE, L_SRC, L_DATE, L_SUMMARY, L_LINK = labels

    for i, item in enumerate(news_items, 1):
        summary = (item.get("summary") or "").strip()
        if len(summary) > 350:
            summary = summary[:350] + "..."
        lines.append(
            f"\n[{i}] {L_TITLE} : {item.get('title','')}\n"
            f"    {L_SRC} : {item.get('source','')}\n"
            f"    {L_DATE} : {item.get('published','')}\n"
            f"    {L_SUMMARY} : {summary}\n"
            f"    {L_LINK} : {item.get('link','')}"
        )
    return "\n".join(lines)


def _configure_client() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GenerationError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)


# 이모지 / 흔한 그림문자 (U+2600~U+27BF, 화살표, 다양한 심볼 블록 포함).
# 본문/제목/태그/alt 에서 모두 잘라낸다.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"   # symbols & pictographs
    "\U0001F600-\U0001F64F"   # emoticons
    "\U0001F680-\U0001F6FF"   # transport & map
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U0001F1E0-\U0001F1FF"   # flags
    "⌀-⏿"
    "⬀-⯿"
    "　〰"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(s: str) -> str:
    if not s:
        return s
    cleaned = _EMOJI_RE.sub("", s)
    # 이모지 제거 후 남은 이중 공백 정리
    return re.sub(r"\s{2,}", " ", cleaned).strip()


_POLLINATIONS_URL_RE = re.compile(
    r'(https://image\.pollinations\.ai/prompt/)([^"\'?\s]+)(\?[^"\'\s]*)?',
    re.IGNORECASE,
)


def _normalize_pollinations_urls(body: str) -> str:
    """Pollinations.ai URL 의 prompt 부분을 URL-encode 한다.

    AI 가 `https://image.pollinations.ai/prompt/data center server?width=...`
    같이 공백 포함된 URL 을 출력해도 HTML 에 들어가면 깨지므로,
    prompt 토큰만 추출해 quote() 처리 후 재조립. 이미 인코딩된 경우는 한 번
    decode 후 다시 인코딩해 이중 인코딩 방지.
    """
    def _encode(m: re.Match) -> str:
        prefix = m.group(1)
        prompt = m.group(2)
        query = m.group(3) or ""
        try:
            decoded = unquote(prompt)
        except Exception:
            decoded = prompt
        encoded = quote(decoded, safe="")
        return f"{prefix}{encoded}{query}"

    return _POLLINATIONS_URL_RE.sub(_encode, body)


def _parse_response(text: str, language: str = "ko") -> GeneratedPost:
    text = text.strip()
    # 모델이 코드펜스를 붙였을 경우 방어적으로 제거
    text = re.sub(r"^```(?:html|HTML)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)

    # 1) TITLE
    m_title = re.search(r"^\s*TITLE\s*:\s*(.+)$", text, flags=re.MULTILINE)
    if not m_title:
        raise GenerationError(
            "TITLE line missing in model output. "
            f"First 200 chars: {text[:200]!r}"
        )
    title = _strip_emoji(m_title.group(1).strip())

    # 2) TAGS (없으면 빈 리스트로 두고 main 단에서 config tags 폴백)
    tags: list[str] = []
    m_tags = re.search(r"^\s*TAGS\s*:\s*(.+)$", text, flags=re.MULTILINE)
    if m_tags:
        raw = m_tags.group(1).strip()
        tags = [
            _strip_emoji(t).strip()
            for t in re.split(r"[,、]", raw)   # , 또는 한국어 쉼표 "、"
        ]
        tags = [t for t in tags if t]              # 빈 토큰 제거
    else:
        logger.warning("TAGS line missing — will fall back to config tags")

    # 3) Body — '---' 구분자 이후 / 없으면 첫 HTML 태그부터
    sep_match = re.search(r"^-{3,}\s*$", text, flags=re.MULTILINE)
    if sep_match:
        body = text[sep_match.end():].lstrip()
    else:
        last_meta = m_tags.end() if m_tags else m_title.end()
        rest = text[last_meta:].lstrip()
        html_match = re.search(r"<(?:h2|h3|p|img|ul|ol)\b", rest)
        body = rest[html_match.start():] if html_match else rest

    # 코드펜스 잔재 한 번 더 제거 + body 내 이모지 잘라내기
    body = re.sub(r"^```(?:html|HTML)?\s*\n", "", body)
    body = re.sub(r"\n```\s*$", "", body)
    body = _strip_emoji(body)

    # Pollinations 이미지 URL 의 prompt 부분 URL-encoding
    # (AI 가 "data center server" 같이 공백 포함 prompt 를 그대로 출력하는 케이스 대응)
    body = _normalize_pollinations_urls(body)

    # 4) 최소 구조 검증
    img_count = len(re.findall(r"<img\b", body))
    if img_count < 2:
        raise GenerationError(
            f"본문 이미지 부족 — 2~3장 필요, 발견 {img_count}개"
        )
    if "<h2" not in body:
        raise GenerationError("<h2> heading missing from generated HTML")

    # 언어별 SEO 섹션 헤딩 패턴
    if language == "en":
        # 헤딩에 "references" 가 포함되면 매칭 (e.g., "Industry References & Signals")
        refs_pattern = r"<h[23][^>]*>[^<]*references?[^<]*</h[23]>"
        # Strategy / Implementation / ROI 등 다양한 헤딩 변형 허용 (long-form 구조)
        strategy_pattern = (
            r"<h[23][^>]*>[^<]*(?:strategic\s+implications|"
            r"strategic\s+implementation|enterprise\s+roi|"
            r"action\s+items|phased\s+rollout|recommendations|"
            r"checklist|what\s+.+\s+should)"
        )
        # Executive Summary 가 포함된 모든 h2 매칭 (e.g., "Executive Summary & Core Takeaways")
        tldr_pattern = r"<h2[^>]*>[^<]*executive\s+summary[^<]*</h2>"
        refs_label, strategy_label, tldr_label = (
            "References", "Strategic Implications / ROI", "Executive Summary"
        )
        re_flags = re.IGNORECASE
    else:
        refs_pattern = r"참고자료"
        strategy_pattern = (
            r"<h3[^>]*>[^<]*(?:대응\s*전략|시사점|체크리스트|준비할|점검)"
        )
        tldr_pattern = r"<h3[^>]*>\s*핵심\s*요약\s*</h3>"
        refs_label, strategy_label, tldr_label = (
            "참고자료", "대응 전략 / 시사점", "핵심 요약"
        )
        re_flags = 0

    if not re.search(refs_pattern, body, flags=re_flags):
        logger.warning("'%s' 섹션 없음 — SEO 규칙 미준수 가능", refs_label)

    has_strategy_heading = bool(re.search(strategy_pattern, body, flags=re_flags))
    if not has_strategy_heading:
        logger.warning(
            "'%s' 섹션 헤딩이 감지되지 않음 — 규칙 5(C) 위반 가능",
            strategy_label,
        )

    # TL;DR — Featured Snippet 핵심
    has_tldr_heading = bool(re.search(tldr_pattern, body, flags=re_flags))
    has_blockquote = "<blockquote" in body
    if not has_tldr_heading:
        logger.warning(
            "'%s' TL;DR 섹션 헤딩이 없음 — 규칙 5(A2) 위반 가능", tldr_label
        )
    elif not has_blockquote:
        logger.warning("'핵심 요약' 섹션이 <blockquote> 로 감싸지지 않음")
    else:
        # blockquote 안의 <li> 가 정확히 3개인지 확인 (느슨한 매칭)
        bq_match = re.search(
            r"<blockquote[^>]*>([\s\S]*?)</blockquote>", body
        )
        if bq_match:
            li_count = len(re.findall(r"<li\b", bq_match.group(1)))
            if li_count != 3:
                logger.warning(
                    "TL;DR <blockquote> 안의 <li> 개수=%d (3개 필요)", li_count
                )

    # 참고자료(1) + Strategy(1) + TL;DR(1) 합쳐 본문엔 <ul> 이 최소 3개 있어야 함.
    ul_count = body.count("<ul")
    if ul_count < 3:
        logger.warning(
            "본문 <ul> 개수 부족 (=%d). TL;DR/Strategy/참고자료 중 일부가 누락 가능",
            ul_count,
        )

    # 기계적 접속사 사용 카운트 (참고용 로그) — 0회 권장
    banned_connectors = ["주목할 만한 점은", "게다가", "또한", "더불어", "한편", "이에 따라"]
    found_connectors = [w for w in banned_connectors if w in body]
    if found_connectors:
        logger.warning(
            "기계적 접속사 사용 감지: %s — 규칙 3 위반 (자연 전환으로 교체 필요)",
            found_connectors,
        )

    return GeneratedPost(title=title, html=body, tags=tags)


def generate_post(
    topic_label: str,
    niche_keyword: str,
    news_items: list[dict],
    language: str = "ko",
    api_key: str | None = None,
    focus_keyword: str | None = None,
    retries: int = 2,
    retry_delay: float = 3.0,
) -> GeneratedPost:
    """Generate a blog post via Gemini.

    language="ko" (default) : Tistory-ready 한국어 글 (기존 SYSTEM_INSTRUCTION)
    language="en"           : Blogger-ready English 글 (SYSTEM_INSTRUCTION_EN,
                              McKinsey 스타일, B2B / Featured Snippet 최적화)
    api_key                 : Multi-key routing — 사이트별 다른 Gemini API key
                              사용. None 이면 GEMINI_API_KEY env var 로 fallback.
    """
    if not news_items:
        raise GenerationError("No news items provided to generator")

    # 언어별 system + user prompt 선택
    if language == "en":
        active_system = SYSTEM_INSTRUCTION_EN
        active_user_template = USER_PROMPT_TEMPLATE_EN
    else:
        active_system = SYSTEM_INSTRUCTION
        active_user_template = USER_PROMPT_TEMPLATE

    # Multi-key routing: 사이트별 키를 우선 사용, 없으면 단일 GEMINI_API_KEY 로 fallback.
    # 동일 프로세스에서 사이트마다 다른 키로 호출 가능하도록 genai.configure 를
    # 매 호출마다 실행 (sequential 실행이라 race condition 없음).
    effective_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not effective_key:
        raise GenerationError(
            "Gemini API key 가 없음 — generate_post(api_key=...) 로 명시 전달 "
            "또는 GEMINI_API_KEY 환경변수 설정 필요."
        )
    genai.configure(api_key=effective_key)

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=active_system,
        generation_config={
            # 0.85 → 0.7 : TITLE/이미지 등 포맷 룰 미준수로 인한 parse 재시도 빈도 감소.
            # 너무 낮추면 표현 다양성이 떨어지므로 0.7 균형점.
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        },
        safety_settings={
            "HARASSMENT": "BLOCK_ONLY_HIGH",
            "HATE_SPEECH": "BLOCK_ONLY_HIGH",
            "SEXUAL": "BLOCK_ONLY_HIGH",
            "DANGEROUS": "BLOCK_ONLY_HIGH",
        },
    )

    news_block_str = _format_news_block(news_items, language=language)
    # 영문 template 은 {keyword} / {news_context} placeholder 를 쓰므로 별칭 매핑.
    # Python str.format 은 미사용 kwarg 를 무시하므로 한국어 path 에도 안전.
    user_prompt = active_user_template.format(
        topic_label=topic_label,
        niche_keyword=niche_keyword,
        news_block=news_block_str,
        keyword=focus_keyword or topic_label,
        news_context=news_block_str,
    )

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        delay = retry_delay   # 이번 시도 실패 후 사용할 sleep 시간
        try:
            response = model.generate_content(user_prompt)
            text = getattr(response, "text", None)
            if not text:
                # response.text raises if blocked; double-check candidates
                fb = getattr(response, "prompt_feedback", None)
                raise GenerationError(
                    f"Empty response from Gemini (prompt_feedback={fb})"
                )
            return _parse_response(text, language=language)
        except GenerationError as e:
            last_err = e
            logger.warning(
                "Generation attempt %d/%d parse-failed: %s",
                attempt + 1, retries + 1, e,
            )
        except Exception as e:
            last_err = e
            if _is_quota_error(e):
                # 429 / quota — 짧은 지연으로는 또 막힘. 강제로 15s 대기 후 재시도.
                delay = QUOTA_RETRY_DELAY
                logger.warning(
                    "Generation attempt %d/%d hit RATE LIMIT (429/quota) — "
                    "sleeping %ds before retry: %s",
                    attempt + 1, retries + 1, int(delay), e,
                )
            else:
                logger.warning(
                    "Generation attempt %d/%d API error: %s",
                    attempt + 1, retries + 1, e,
                )

        if attempt < retries:
            time.sleep(delay)

    raise GenerationError(f"All generation attempts failed: {last_err}")

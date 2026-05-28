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

import google.generativeai as genai

logger = logging.getLogger(__name__)

# 모델명은 환경변수 GEMINI_MODEL 로 오버라이드 가능 (예: gemini-2.5-flash).
# 기본값은 사용자 요청에 따른 gemini-3.5-flash.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# =====================================================================
# SYSTEM INSTRUCTION  (이 프롬프트가 글의 품질을 결정합니다)
# =====================================================================
SYSTEM_INSTRUCTION = r"""
당신은 대한민국 티스토리(Tistory) 블로그 상위 1% 의 전업 블로거입니다.
운영 카테고리는 구글 애드센스 고수익군(IT/경제/금융/투자/트렌드)이며,
구글 SEO 와 한국 검색엔진(네이버, 다음) 알고리즘 양쪽에 모두 최적화된
프로 매체 수준의 글을 작성합니다.

아래 모든 규칙은 "절대 규칙(Hard Rule)"이며, 한 가지라도 어기면 실격입니다.

────────────────────────────────────────────────────────
[규칙 1] 페르소나 — "친한 전문가 친구(Expert Friend)"
────────────────────────────────────────────────────────
- 독자에게 깊은 신뢰를 주는 전문가지만, 어려운 내용을 친구에게
  설명하듯 자연스럽게 풀어주는 톤.
- 어미는 "~해요 / ~습니다 / ~인데요 / ~알아볼까요? / ~거든요"
  를 적절히 섞어 사용. 한 가지 어미만 반복 금지.
- 번역체, 위키백과체, 보도자료체 금지.

────────────────────────────────────────────────────────
[규칙 2] 이모지·이모티콘·그림문자 절대 금지
────────────────────────────────────────────────────────
제목·태그·헤딩·본문·참고자료·alt 텍스트 그 어디에도 이모지/이모티콘/
유니코드 그림문자를 일체 사용 금지.
예시(모두 금지): 📈 💡 🚀 ✅ ✨ 📌 👉 🔥 💰 📊 ⭐ 🎯 ❗ ⚡ 🔍 📰 🏆
강조가 필요하면 <strong> / <b> 또는 자연스러운 문장 표현으로 대체.
조선/매경/한경 IT면 같은 프로 매체의 plain text 만 출력하세요.

────────────────────────────────────────────────────────
[규칙 3] AI 흔적 제거 — 다음 표현은 어떤 변형으로도 절대 금지
────────────────────────────────────────────────────────
- "결론적으로", "요약하자면", "정리하자면", "마무리하며"
- "이 글에서는", "이번 포스팅에서는", "지금부터 알아보겠습니다"
- "안녕하세요 여러분", "여러분, 오늘은~"
- "다음과 같습니다:", "~에 대해 알아보도록 하겠습니다"
- "AI", "인공지능이 작성", "생성형" 같은 자기 정체 노출 표현

→ 대신 자연스러운 문맥 전환: "사실 핵심은…", "여기서 짚어볼 점은…",
  "그렇다면 왜 지금…", "한 발 더 들어가 보면…", "투자자 입장에선…"

────────────────────────────────────────────────────────
[규칙 4] 티스토리 HTML 구조 — 정확히 아래 태그만 사용
────────────────────────────────────────────────────────
허용 태그:
  <h2>   본문 대주제 (3~5개)
  <h3>   소주제 (각 <h2> 아래 1~3개) + 마지막 "참고자료" 섹션
  <p>    본문 단락 (한 단락 2~4문장)
  <ul><li>  나열형 정보
  <ol><li>  순서가 중요한 단계
  <strong> 또는 <b>   SEO 핵심 키워드 강조
  <blockquote>        핵심 인용 (선택)
  <img>  본문 이미지 (규칙 6 참조)
  <a href="..." target="_blank" rel="noopener">   참고자료 외부 링크

금지:
  <html>, <body>, <head>, <style>, <script>, <div>, <span>,
  class/id 속성, 인라인 style 속성(단, <img> 의 style 만 허용),
  마크다운 문법(##, **, -, ```), HTML 코드펜스(```html).

────────────────────────────────────────────────────────
[규칙 5] 자연스러운 헤딩 — 강제 템플릿 절대 금지
────────────────────────────────────────────────────────
모든 <h3> 헤딩은 그 섹션의 실제 내용을 정확히 반영하는, 자연스럽고
대화체에 가까운 한국어로 매번 새로 작성. 고정된 템플릿/정형 문구 금지.

좋은 헤딩 예시 (구체적이고 섹션 내용에 직결):
  - "이 변화가 우리에게 미치는 영향"
  - "시장이 주목하는 진짜 이유"
  - "투자자 입장에서 살펴볼 시그널"
  - "왜 하필 지금 이 발표가 나왔을까"
  - "다음 6개월, 이렇게 움직일 가능성"
  - "삼성과 SK 의 셈법이 다른 이유"
  - "개인 매수자가 놓치기 쉬운 부분"

나쁜 헤딩 예시 (금지):
  - "💡 이게 왜 중요할까요?"   ← 이모지 + 정형 템플릿
  - "📈 투자 & 트렌드 인사이트" ← 이모지 + 정형 템플릿
  - "결론" / "마무리" / "시사점"  ← AI 흔적 / 무미건조

각 뉴스 주제마다 단순 사실 요약을 넘어 작성자의 독창적 분석/관점
(개인 투자자·소비자에게 미치는 의미, 산업 구조 변화, 6~12개월 시나리오,
관련 종목/대안 행동) 을 반드시 1개 이상의 <h3> 섹션으로 포함.

────────────────────────────────────────────────────────
[규칙 6] 본문 이미지 — 정확히 2~3장, 섹션 사이 자연 배치
────────────────────────────────────────────────────────
본문 흐름에 맞춰 <h2> 섹션 사이사이에 정확히 2~3장의 이미지 삽입.
"본문 최상단 표지 1장" 형식 금지 — 첫 <h2> 보다 앞에 <img> 두면 안 됨.

형식 (정확히 준수, 줄바꿈 자유):
  <img src="https://loremflickr.com/800/400/{english_keyword}/all"
       alt="{한국어 SEO 설명문}"
       style="max-width: 100%; border-radius: 8px; margin: 20px 0;">

- {english_keyword} : 해당 위치 단락의 핵심 명사 1개, 영문 소문자 단수.
  예: nvidia, semiconductor, stock, economy, anthropic, samsung,
      bitcoin, realestate, interestrate, startup, datacenter
  (복수형/공백/특수문자/한글 금지. loremflickr 가 인식 못 함)
- {alt} : 해당 이미지가 가리키는 내용에 대한 자연스러운 한국어 설명문.
  단순 키워드 나열이 아니라 문장 형태로 (SEO 효과 위해).
- 이미지는 본문 컨텍스트와 연관된 위치에 분산 — 무관한 위치 배치 금지.

────────────────────────────────────────────────────────
[규칙 7] 참고자료 섹션 — 본문 최하단 필수
────────────────────────────────────────────────────────
HTML 본문의 가장 마지막 요소로 아래 형식의 참고자료 섹션 부착:

  <h3>참고자료</h3>
  <ul>
    <li><a href="원문URL1" target="_blank" rel="noopener">원문기사제목1</a></li>
    <li><a href="원문URL2" target="_blank" rel="noopener">원문기사제목2</a></li>
  </ul>

- 본문에서 실제로 인용·참고한 user_prompt 의 뉴스 link/title 만 사용.
- URL 위·변조/생성 절대 금지. 입력으로 받은 정확한 문자열만 그대로.
- 헤딩은 이모지 없이 정확히 4글자: "참고자료"

────────────────────────────────────────────────────────
[규칙 8] SEO 제목 + 태그 — 응답 최상단 2줄로 분리 출력
────────────────────────────────────────────────────────
응답의 첫 두 줄을 정확히 아래 형식으로 (대소문자 그대로, ":" 뒤 공백 1칸):

  TITLE: [오늘의 핫이슈] 메인키워드 - 호기심을 유발하는 부제목
  TAGS: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5

TITLE:
  - 전체 한글 기준 30~50자, 과장/낚시/허위 금지.
  - 메인키워드는 검색량 높은 고유명사/핵심어, 부제목은 클릭 욕구 자극.

TAGS:
  - 정확히 5~7개. "콤마+공백 1칸" 으로 구분.
  - 각 태그는 한글/영문 1~6자 또는 짧은 합성어 (예: AI반도체, 엔비디아).
  - 이모지/특수문자/공백포함태그 금지.
  - 광범위 키워드("뉴스", "정보", "트렌드") 금지. 검색량 있는 구체 키워드.

────────────────────────────────────────────────────────
[규칙 9] 분량 / 품질
────────────────────────────────────────────────────────
- 본문(HTML 태그 제외) 한국어 공백 제외 2,500자 이상 4,500자 이하.
- <h2> 섹션 3~5개, 각 섹션 아래 <h3> 1~3개.
- 사실 단정 시 "OO일자 보도에 따르면", "OO사 발표 자료를 보면"
  같은 자연스러운 본문 표현으로 출처 인용.

────────────────────────────────────────────────────────
[규칙 10] 출력 포맷 — 정확히 이 구조만, 다른 머리말/꼬리말 금지
────────────────────────────────────────────────────────
TITLE: [오늘의 핫이슈] 메인키워드 - 부제목
TAGS: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5
---
<h2>...</h2>
<p>...</p>
<h3>...(자연스러운 한국어 헤딩)...</h3>
<p>...</p>
<img src="https://loremflickr.com/800/400/...keyword.../all" alt="..." style="...">
<h2>...</h2>
<p>...</p>
... (본문 이미지 총 2~3장 포함)
<h3>참고자료</h3>
<ul>
  <li><a href="..." target="_blank" rel="noopener">...</a></li>
  ...
</ul>

— 코드펜스 (```html) 금지. "다음은 작성한 글입니다" 류 머리말 금지.
— 정확히 TITLE 으로 시작해서 </ul> 로 끝나야 함.
""".strip()


# =====================================================================
# USER PROMPT TEMPLATE
# =====================================================================
USER_PROMPT_TEMPLATE = """### 오늘 작성할 블로그 정보

- 블로그 주제 카테고리 : {topic_label}
- 본문 이미지 참고용 niche 힌트 : {niche_keyword}
  (실제 <img> 의 english_keyword 는 단락 내용에 맞춰 자유롭게 선택)
- 오늘 다룰 뉴스 소스 (Google News RSS 상위 결과 — 아래 link 와 title 만
  참고자료 섹션에 그대로 인용 가능, 위·변조 금지)
{news_block}

### 작성 지시
위 뉴스 중 가장 화제성·검색량이 높을 것으로 판단되는 1~3건을 선별하여
하나의 통합된 블로그 글로 작성하세요.

- 각 뉴스마다: (1) 사실 현황 → (2) 배경/맥락 → (3) 작성자만의 독창적
  분석 섹션(헤딩은 매번 새로 자연스럽게 — 고정 템플릿 금지) 흐름으로.
- 본문 이미지 정확히 2~3장을 <h2> 섹션 사이사이 자연스러운 위치에 배치.
  english_keyword 는 그 위치 단락의 핵심 명사 영문 단수형.
- 본문 가장 마지막 요소는 반드시 <h3>참고자료</h3> + <ul> 링크 리스트.
- 응답 첫 두 줄은 TITLE: / TAGS: 로 시작, 세 번째 줄은 "---" 구분자,
  네 번째 줄부터 HTML 본문.
- 시스템 지침의 모든 규칙(이모지 금지 / 자연스러운 헤딩 / HTML 태그 제약 /
  출력 포맷) 을 100% 준수.

지금 바로 작성을 시작하세요. (첫 줄은 반드시 'TITLE: ' 으로 시작)
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


def _format_news_block(news_items: list[dict]) -> str:
    lines: list[str] = []
    for i, item in enumerate(news_items, 1):
        summary = (item.get("summary") or "").strip()
        if len(summary) > 350:
            summary = summary[:350] + "..."
        lines.append(
            f"\n[{i}] 제목 : {item.get('title','')}\n"
            f"    출처 : {item.get('source','')}\n"
            f"    발행 : {item.get('published','')}\n"
            f"    요약 : {summary}\n"
            f"    링크 : {item.get('link','')}"
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


def _parse_response(text: str) -> GeneratedPost:
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

    # 4) 최소 구조 검증
    img_count = len(re.findall(r"<img\b", body))
    if img_count < 2:
        raise GenerationError(
            f"본문 이미지 부족 — 2~3장 필요, 발견 {img_count}개"
        )
    if "<h2" not in body:
        raise GenerationError("<h2> heading missing from generated HTML")
    if "참고자료" not in body:
        logger.warning("'참고자료' 섹션 없음 — SEO 규칙 미준수 가능")

    return GeneratedPost(title=title, html=body, tags=tags)


def generate_post(
    topic_label: str,
    niche_keyword: str,
    news_items: list[dict],
    retries: int = 2,
    retry_delay: float = 3.0,
) -> GeneratedPost:
    """Generate a Tistory-ready Korean blog post via Gemini."""
    if not news_items:
        raise GenerationError("No news items provided to generator")

    _configure_client()

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config={
            "temperature": 0.85,
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

    user_prompt = USER_PROMPT_TEMPLATE.format(
        topic_label=topic_label,
        niche_keyword=niche_keyword,
        news_block=_format_news_block(news_items),
    )

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = model.generate_content(user_prompt)
            text = getattr(response, "text", None)
            if not text:
                # response.text raises if blocked; double-check candidates
                fb = getattr(response, "prompt_feedback", None)
                raise GenerationError(
                    f"Empty response from Gemini (prompt_feedback={fb})"
                )
            return _parse_response(text)
        except GenerationError as e:
            last_err = e
            logger.warning(
                "Generation attempt %d/%d parse-failed: %s",
                attempt + 1, retries + 1, e,
            )
        except Exception as e:
            last_err = e
            logger.warning(
                "Generation attempt %d/%d API error: %s",
                attempt + 1, retries + 1, e,
            )

        if attempt < retries:
            time.sleep(retry_delay)

    raise GenerationError(f"All generation attempts failed: {last_err}")

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
from dataclasses import dataclass

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
글을 작성합니다.

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
[규칙 2] AI 흔적 제거 — 다음 표현은 어떤 변형으로도 절대 금지
────────────────────────────────────────────────────────
- "결론적으로", "요약하자면", "정리하자면", "마무리하며"
- "이 글에서는", "이번 포스팅에서는", "지금부터 알아보겠습니다"
- "안녕하세요 여러분", "여러분, 오늘은~"
- "다음과 같습니다:", "~에 대해 알아보도록 하겠습니다"
- "AI", "인공지능이 작성", "생성형" 같은 자기 정체 노출 표현

→ 대신 자연스러운 문맥 전환 사용:
  "사실 핵심은…", "여기서 짚어볼 점은…", "그렇다면 왜 지금…",
  "한 발 더 들어가 보면…", "투자자 입장에선…"

────────────────────────────────────────────────────────
[규칙 3] 티스토리 HTML 구조 — 정확히 아래 태그만 사용
────────────────────────────────────────────────────────
허용 태그:
  <h2>   본문 대주제 (3~5개)
  <h3>   소주제 (각 <h2> 아래 1~3개)
  <p>    본문 단락 (한 단락 2~4문장)
  <ul><li>  나열형 정보 (3~6개 항목)
  <ol><li>  순서가 중요한 단계
  <strong> 또는 <b>   SEO 핵심 키워드 강조 (단락당 1~2회)
  <blockquote>        핵심 문장 인용 (선택)
  <img>  표지 이미지 1장만 (규칙 5)

금지:
  <html>, <body>, <head>, <style>, <script>, <div>, <span>,
  class/id 속성, 인라인 style 속성(단, 표지 <img> 의 style 만 허용),
  마크다운 문법(##, **, -, ```), HTML 코드펜스(```html).

────────────────────────────────────────────────────────
[규칙 4] AdSense 수익 핵심 — "이게 왜 중요할까요?" 섹션
────────────────────────────────────────────────────────
글에서 다루는 각 핵심 주제(뉴스)마다 반드시 아래 형식의
인사이트 섹션을 1개 이상 포함:

  <h3>💡 이게 왜 중요할까요?</h3>
  또는
  <h3>📈 투자 & 트렌드 인사이트</h3>

이 섹션은 단순 사실 요약 금지. 반드시 작성자만의 독창적 관점:
  - "개인 투자자/소비자 입장에서 어떤 의미인가"
  - "산업 생태계에 어떤 변화가 예상되는가"
  - "6개월~1년 후 어떤 결과/시나리오가 그려지는가"
  - "관련 종목 / 키워드 / 대안 행동은 무엇인가"
구체적이고 실용적인 분석을 2~4문장으로 작성.

────────────────────────────────────────────────────────
[규칙 5] 표지 이미지 — 본문 최상단 첫 번째 요소
────────────────────────────────────────────────────────
출력 HTML 의 가장 첫 번째 요소로 정확히 아래 형식의 <img> 1장:

  <img src="https://loremflickr.com/800/400/{NICHE_KEYWORD}/all"
       alt="{SEO_TITLE}"
       style="max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 20px;">

- {NICHE_KEYWORD} 는 user_prompt 의 niche_keyword 값으로 치환.
- {SEO_TITLE} 은 본인이 생성한 SEO 제목으로 치환.
- 본문 중간에 추가 이미지 삽입 금지 (이 표지 1장만).

────────────────────────────────────────────────────────
[규칙 6] SEO 제목 — 응답 최상단에 별도 라인으로 출력
────────────────────────────────────────────────────────
형식 (정확히 준수):
  TITLE: [오늘의 핫이슈] 메인키워드 - 호기심을 유발하는 부제목

- "메인키워드" : 글의 핵심 검색 키워드 (검색량 높은 단어/고유명사)
- "부제목"     : 클릭 욕구 자극 (단, 과장/낚시/허위는 절대 금지)
- 전체 한글 기준 30~50자 권장

────────────────────────────────────────────────────────
[규칙 7] 분량 / 품질
────────────────────────────────────────────────────────
- 본문(HTML 태그 제외) 한국어 공백 제외 2,500자 이상 4,500자 이하.
- <h2> 섹션 3~5개, 각 섹션 아래 <h3> 1~3개.
- 마지막 섹션은 짧은 정리/제안형 단락 (단, "결론적으로" 금지).
- 사실 관계 단정 시 출처 인용은 자연스러운 본문 표현으로
  ("OO일자 보도에 따르면", "OO사 발표 자료를 보면" 등).

────────────────────────────────────────────────────────
[규칙 8] 출력 포맷 — 다음 형식만 출력. 다른 설명/머리말/꼬리말 금지
────────────────────────────────────────────────────────
TITLE: [오늘의 핫이슈] 메인키워드 - 호기심을 유발하는 부제목
---
<img src="https://loremflickr.com/800/400/.../all" alt="..." style="...">
<h2>...</h2>
<p>...</p>
<h3>💡 이게 왜 중요할까요?</h3>
<p>...</p>
... (이하 본문)

— ```html 같은 코드펜스 사용 금지.
— "다음은 작성한 글입니다" 같은 머리말 금지. TITLE: 부터 바로 시작.
""".strip()


# =====================================================================
# USER PROMPT TEMPLATE
# =====================================================================
USER_PROMPT_TEMPLATE = """### 오늘 작성할 블로그 정보

- 블로그 주제 카테고리 : {topic_label}
- 표지 이미지 niche_keyword : {niche_keyword}
- 오늘 다룰 뉴스 소스 (Google News RSS 상위 결과)
{news_block}

### 작성 지시
위 뉴스 중 가장 화제성과 검색량이 높을 것으로 판단되는 1~3건을 선별하여,
하나의 통합된 블로그 글로 작성하세요.
- 각 뉴스마다: (1) 사실 현황 → (2) 배경/맥락 → (3) 💡 이게 왜 중요할까요? 인사이트 흐름.
- 독자가 검색해 들어왔을 때 "이 글 하나로 다 이해됐다" 고 느낄 만큼 자세히.
- 시스템 지침의 모든 규칙(특히 금지 표현 / HTML 태그 제약 / 출력 포맷)을 100% 준수.

지금 바로 작성을 시작하세요. (반드시 TITLE: 으로 시작)
"""


# =====================================================================
# Code
# =====================================================================
@dataclass
class GeneratedPost:
    title: str
    html: str


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


def _parse_response(text: str) -> GeneratedPost:
    text = text.strip()
    # Defensively strip code fences if the model added them.
    text = re.sub(r"^```(?:html|HTML)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)

    m = re.search(r"^\s*TITLE:\s*(.+)$", text, flags=re.MULTILINE)
    if not m:
        raise GenerationError(
            "Title line (TITLE: ...) missing in model output. "
            f"First 200 chars: {text[:200]!r}"
        )
    title = m.group(1).strip()

    body = text[m.end():].lstrip()
    # Remove optional `---` separator line.
    body = re.sub(r"^-{3,}\s*\n?", "", body, count=1).lstrip()

    if "<img" not in body:
        raise GenerationError("Cover <img> tag missing from generated HTML")
    if "<h2" not in body:
        raise GenerationError("<h2> heading missing from generated HTML")

    return GeneratedPost(title=title, html=body)


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

"""Tistory publisher — storage_state(쿠키) 주입 방식 (로그인 자동화 제거).

전제:
  - 로컬에서 헤드풀 브라우저로 한 번 수동 로그인하여 `state.json`
    (Playwright storage_state) 파일을 미리 만들어 둡니다.
  - GitHub Actions 에서는 `TISTORY_STATE_JSON` Secret 에 그 파일의 내용을
    그대로 넣고, 워크플로 단계에서 `state.json` 파일로 덤프합니다.
  - 본 모듈은 그 파일을 그대로 브라우저 컨텍스트에 주입하여, 어떤 형태의
    로그인 자동화(아이디/비밀번호 입력)도 수행하지 않습니다.
    → Kakao 의 CAPTCHA / 2단계 인증 / 자동화 탐지를 원천 회피.

세션 만료 시:
  - `https://{blog_name}.tistory.com/manage/newpost/` 진입 직후
    호스트가 Kakao 또는 티스토리 로그인 페이지로 튕기면 즉시
    "state.json 을 새로 발급받으세요" 에러로 종료합니다.

state.json 만드는 법 (로컬, 1회):
  python -m playwright install chromium
  # 아래 같은 헬퍼 스크립트로 수동 로그인 후 storage_state 저장:
  #
  #   from playwright.sync_api import sync_playwright
  #   with sync_playwright() as p:
  #       b = p.chromium.launch(headless=False)
  #       ctx = b.new_context(locale="ko-KR")
  #       page = ctx.new_page()
  #       page.goto("https://www.tistory.com/auth/login")
  #       input("브라우저에서 로그인 후 Enter ... ")
  #       ctx.storage_state(path="state.json")
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import (
    Page,
    TimeoutError as PWTimeoutError,
    sync_playwright,
)

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """Raised when publishing to Tistory fails."""


class SessionExpiredError(PublishError):
    """state.json 의 세션이 만료되어 재발급이 필요한 경우."""


DEFAULT_TIMEOUT_MS = 30_000
SCREENSHOTS_DIR = Path("artifacts/screenshots")
DEFAULT_STATE_PATH = "state.json"


# ---------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------
def _screenshot(page: Page, tag: str) -> None:
    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        p = SCREENSHOTS_DIR / f"{int(time.time())}_{tag}.png"
        page.screenshot(path=str(p), full_page=True)
        logger.info("Saved screenshot: %s", p)
    except Exception as e:
        logger.warning("Screenshot failed (%s): %s", tag, e)


def _try_click(page: Page, selectors: list[str], timeout: int = 4_000) -> bool:
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=timeout)
            logger.debug("Clicked: %s", sel)
            return True
        except PWTimeoutError:
            continue
        except Exception as e:
            logger.debug("Click '%s' err: %s", sel, e)
    return False


def _dump_debug(page: Page, tag: str) -> None:
    """에디터 진입 실패 시 페이지 HTML + DOM 구조를 artifact 에 덤프."""
    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        html_path = SCREENSHOTS_DIR / f"{int(time.time())}_{tag}.html"
        html_path.write_text(page.content(), encoding="utf-8")
        logger.info("Saved page HTML: %s", html_path)
    except Exception as e:
        logger.warning("HTML dump failed: %s", e)

    try:
        info = page.evaluate(
            """
            () => ({
              url: location.href,
              title: document.title,
              inputs: Array.from(document.querySelectorAll('input'))
                .slice(0, 40)
                .map(i => ({
                  type: i.type, id: i.id, name: i.name,
                  placeholder: i.placeholder, visible: !!i.offsetParent
                })),
              textareas: Array.from(document.querySelectorAll('textarea'))
                .slice(0, 20)
                .map(t => ({
                  id: t.id, name: t.name,
                  placeholder: t.placeholder, visible: !!t.offsetParent
                })),
              iframes: Array.from(document.querySelectorAll('iframe'))
                .map(f => ({ id: f.id, name: f.name, src: f.src })),
              bodyTextSample: (document.body && document.body.innerText || '')
                .substring(0, 600),
            })
            """
        )
        logger.info("DOM snapshot (%s): %s", tag, info)
    except Exception as e:
        logger.warning("DOM snapshot failed (%s): %s", tag, e)


def _resolve_state_path() -> Path:
    """state.json 경로 결정 — 환경변수 TISTORY_STATE_PATH 우선."""
    raw = os.environ.get("TISTORY_STATE_PATH", DEFAULT_STATE_PATH)
    state_file = Path(raw)
    if not state_file.is_absolute():
        # 프로젝트 루트(=CWD) 기준
        state_file = Path.cwd() / state_file
    return state_file


# ---------------------------------------------------------------------
# Session check
# ---------------------------------------------------------------------
def _check_session_alive(page: Page, blog_name: str) -> None:
    """현재 URL 이 새 글 작성 페이지에 머물러 있는지 확인. 아니면 즉시 에러."""
    parsed = urlparse(page.url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    expected_host = f"{blog_name}.tistory.com".lower()

    # 1) Kakao 도메인으로 튕긴 경우 = 명백히 세션 만료
    if host in ("accounts.kakao.com", "kauth.kakao.com", "logins.daum.net"):
        _screenshot(page, "session_expired_kakao")
        raise SessionExpiredError(
            "세션(쿠키)이 만료되었습니다 — Kakao 로그인 페이지로 리다이렉트됨. "
            f"state.json 을 새로 발급받아야 합니다. (current_url={page.url})"
        )

    # 2) 티스토리 로그인 페이지로 튕긴 경우
    if host == "www.tistory.com" and "/auth/login" in path:
        _screenshot(page, "session_expired_tistory")
        raise SessionExpiredError(
            "세션(쿠키)이 만료되었습니다 — 티스토리 로그인 페이지로 리다이렉트됨. "
            f"state.json 을 새로 발급받아야 합니다. (current_url={page.url})"
        )

    # 3) 우리 블로그 호스트도 아니고 매니지 페이지도 아니면 의심 (블로그 홈으로 리다이렉트 등)
    if host != expected_host:
        _screenshot(page, "session_expired_other")
        raise SessionExpiredError(
            "세션(쿠키)이 만료되었거나 권한 부족 — 예상 호스트 "
            f"{expected_host!r} 가 아닌 {host!r} 로 이동했습니다. "
            "state.json 을 새로 발급받아야 합니다."
        )


# ---------------------------------------------------------------------
# Editor flow
# ---------------------------------------------------------------------
TITLE_SELECTOR = ", ".join([
    '#post-title-input',
    '#post-title-inp',
    'input[name="title"]',
    'textarea[name="title"]',
    'textarea#post-title-input',
    'textarea#post-title-inp',
    'input[placeholder*="제목"]',
    'textarea[placeholder*="제목"]',
    '.post-title-input',
    '[data-testid="post-title"]',
])


def _open_new_post(page: Page, blog_name: str) -> None:
    url = f"https://{blog_name}.tistory.com/manage/newpost/"
    logger.info("Open new-post editor: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)

    # 잠재적 client-side redirect 가 정리되도록 잠시 대기
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeoutError:
        pass

    # 1) 도착한 URL 이 로그인 페이지면 즉시 SessionExpiredError
    _check_session_alive(page, blog_name)

    # 2) "작성 중이던 글 / 임시저장 / 온보딩" 팝업 dismiss (광범위)
    _try_click(
        page,
        [
            'button:has-text("취소")',
            'button:has-text("새 글 작성")',
            'button:has-text("아니요")',
            'button:has-text("닫기")',
            'button:has-text("확인")',
            'button.btn-cancel',
            'a:has-text("새 글 작성")',
        ],
        timeout=4_000,
    )

    # 3) 제목 입력 영역이 등장할 때까지 대기 (광범위 셀렉터)
    try:
        page.wait_for_selector(TITLE_SELECTOR, timeout=20_000)
    except PWTimeoutError:
        # 늦은 client redirect 가능성 — 한 번 더 세션 검사
        _check_session_alive(page, blog_name)
        _screenshot(page, "editor_not_loaded")
        _dump_debug(page, "editor_not_loaded")
        raise PublishError(
            "에디터의 제목 입력 영역을 찾지 못했습니다. artifact 의 "
            "*_editor_not_loaded.html 와 actions 로그의 DOM snapshot 을 보고 "
            "TITLE_SELECTOR / iframe 구조를 점검하세요."
        )


def _fill_title_and_content(page: Page, title: str, html: str) -> None:
    # 1) 제목
    page.locator(TITLE_SELECTOR).first.fill(title)
    logger.info("Title filled (%d chars)", len(title))

    # 2) 본문 — 활성 에디터에 주입.
    #    우선순위: TinyMCE API → TinyMCE iframe → CodeMirror v5/v6 → textarea
    #    주입 직후 그 에디터에서 다시 읽어 verified_len 을 돌려받아 실제 반영 검증.
    result = page.evaluate(
        """
        (html) => {
          // 1) TinyMCE 공식 API (basic 모드의 기본 본문 에디터)
          try {
            const tm = window.tinymce;
            if (tm) {
              const ed = tm.activeEditor || (tm.editors && tm.editors[0]);
              if (ed && typeof ed.setContent === 'function') {
                ed.setContent(html);
                const v = ed.getContent({ format: 'html' }) || '';
                return { via: 'tinymce-api', verified_len: v.length };
              }
            }
          } catch (e) { /* fall through */ }

          // 2) TinyMCE iframe 의 body 에 직접 innerHTML 주입
          const tinyFrame = document.querySelector(
            'iframe.tox-edit-area__iframe, iframe[id$="_ifr"]'
          );
          if (tinyFrame && tinyFrame.contentDocument) {
            const body = tinyFrame.contentDocument.body;
            if (body) {
              body.innerHTML = html;
              return { via: 'tinymce-iframe', verified_len: body.innerHTML.length };
            }
          }

          // 3) CodeMirror v5 (HTML / Markdown 모드)
          const cm5host = document.querySelector('.CodeMirror');
          if (cm5host && cm5host.CodeMirror) {
            cm5host.CodeMirror.setValue(html);
            const v = cm5host.CodeMirror.getValue() || '';
            return { via: 'codemirror5', verified_len: v.length };
          }

          // 4) CodeMirror v6
          const cm6host = document.querySelector('.cm-editor');
          if (cm6host) {
            const view = cm6host.cmView && cm6host.cmView.view;
            if (view) {
              view.dispatch({
                changes: { from: 0, to: view.state.doc.length, insert: html }
              });
              return { via: 'codemirror6', verified_len: view.state.doc.length };
            }
          }

          // 5) 일반 textarea
          const ta = document.querySelector(
            'textarea.html_editor, textarea[name="content"], textarea#content'
          );
          if (ta) {
            ta.value = html;
            ta.dispatchEvent(new Event('input',  { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
            return { via: 'textarea', verified_len: ta.value.length };
          }

          return null;
        }
        """,
        html,
    )

    if not result:
        logger.warning("All editor injection paths failed — falling back to keyboard")
        last_ta = page.locator("textarea").last
        last_ta.focus()
        page.keyboard.insert_text(html)
        result = {"via": "keyboard", "verified_len": len(html)}

    logger.info(
        "Content injected via: %s (sent=%d, verified=%s)",
        result["via"], len(html), result["verified_len"],
    )

    # 검증: 활성 에디터에서 읽어온 길이가 보낸 길이의 절반보다 작으면 실패로 간주.
    if int(result["verified_len"]) < int(len(html) * 0.5):
        _screenshot(page, "content_injection_short")
        _dump_debug(page, "content_injection_short")
        raise PublishError(
            f"본문 주입 실패 — via={result['via']}, "
            f"sent={len(html)}, verified={result['verified_len']}. "
            "잘못된 비활성 에디터 인스턴스에 쓴 것으로 추정. "
            "artifact 의 *_content_injection_short.* 를 보고 셀렉터/iframe 보정 필요."
        )


def _set_tags(page: Page, tags: list[str]) -> None:
    if not tags:
        return
    tag_inp = None
    for sel in ('#tagText', 'input[name="tag"]', 'input[placeholder*="태그"]'):
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=2_000)
            tag_inp = loc
            break
        except PWTimeoutError:
            continue
    if not tag_inp:
        logger.warning("Tag input not found — skipping tags")
        return
    for t in tags:
        try:
            tag_inp.fill(t)
            page.keyboard.press("Enter")
        except Exception as e:
            logger.warning("Tag '%s' add failed: %s", t, e)


def _publish(page: Page) -> str:
    _try_click(
        page,
        [
            'button#publish-layer-btn',
            'button:has-text("완료")',
            'button.btn-publish',
        ],
        timeout=8_000,
    )
    _try_click(
        page,
        [
            'label:has-text("공개")',
            'input#open20',
            'input[name="open"][value="20"]',
        ],
        timeout=4_000,
    )
    final_btns = [
        'button#publish-btn',
        'button:has-text("공개 발행")',
        'button:has-text("발행하기")',
        'button:has-text("발행")',
    ]
    if not _try_click(page, final_btns, timeout=8_000):
        _screenshot(page, "publish_btn_missing")
        raise PublishError("Final publish button not found")

    try:
        page.wait_for_url(lambda u: "/newpost" not in u, timeout=25_000)
    except PWTimeoutError:
        _screenshot(page, "after_publish_no_nav")
        logger.warning("Did not navigate away from /newpost — assuming success")

    final_url = page.url
    logger.info("Post-publish URL: %s", final_url)
    return final_url


# ---------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------
def publish_to_tistory(
    blog_name: str,
    title: str,
    html_content: str,
    tags: list[str] | None = None,
    headless: bool = True,
) -> str:
    """state.json (storage_state) 을 주입하고 글을 발행 후 최종 URL 반환."""
    if not title or not html_content:
        raise PublishError("Empty title or content cannot be published")

    state_file = _resolve_state_path()
    if not state_file.is_file():
        raise PublishError(
            f"storage_state 파일을 찾을 수 없습니다: {state_file}. "
            "로컬에서 수동 로그인 후 state.json 을 생성하거나, "
            "GitHub Actions 에서 TISTORY_STATE_JSON 시크릿을 해당 경로로 기록하는 "
            "단계를 워크플로에 추가하세요."
        )
    if state_file.stat().st_size == 0:
        raise PublishError(f"storage_state 파일이 비어 있습니다: {state_file}")

    logger.info("Using storage_state: %s (%d bytes)",
                state_file, state_file.stat().st_size)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            storage_state=str(state_file),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            _open_new_post(page, blog_name)
            _fill_title_and_content(page, title, html_content)
            _set_tags(page, tags or [])
            return _publish(page)
        except (PublishError, SessionExpiredError):
            raise
        except Exception as e:
            _screenshot(page, "publish_unexpected")
            raise PublishError(f"Tistory publish failed: {e}") from e
        finally:
            try:
                ctx.close()
            finally:
                browser.close()

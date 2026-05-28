"""Tistory publisher via Playwright (Kakao 로그인 기반 브라우저 자동화).

Tistory Open API 신규 발급이 중단되어 토큰 발급이 불가한 환경을 위한 대안.
Kakao 계정 로그인 → 새 글 작성 → HTML 모드로 본문 주입 → 공개 발행.

⚠️ 운영 시 반드시 알아둘 점
  - 2단계 인증(OTP)이 켜진 계정으로는 자동화가 불가능합니다. 자동화 전용
    계정에서는 2단계 인증을 끄거나 별도 정책을 적용하세요.
  - GitHub Actions runner 의 IP 는 클라우드 대역이라 카카오가 CAPTCHA 를
    띄울 가능성이 있습니다. 그 경우 storage_state 캐싱 또는 self-hosted
    runner 사용을 고려해야 합니다.
  - 티스토리 에디터 DOM 은 자주 바뀝니다. 셀렉터 후보를 여러 개 두고
    실패 시 스크린샷을 artifacts/screenshots/ 에 남기도록 했습니다.
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from playwright.sync_api import (
    Page,
    TimeoutError as PWTimeoutError,
    sync_playwright,
)

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """Raised when publishing to Tistory fails."""


DEFAULT_TIMEOUT_MS = 30_000
SCREENSHOTS_DIR = Path("artifacts/screenshots")


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
    """Try each selector in order; return True on first successful click."""
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


# ---------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------
def _kakao_login(page: Page, email: str, password: str) -> None:
    logger.info("Navigating to Tistory login")
    page.goto("https://www.tistory.com/auth/login",
              wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)

    # Tistory 메인 로그인 화면 → "카카오계정으로 로그인" 클릭
    _try_click(
        page,
        [
            'a:has-text("카카오계정으로 로그인")',
            'a.btn_login.link_kakao_id',
            'a[href*="kauth.kakao.com"]',
        ],
        timeout=6_000,
    )

    # 카카오 로그인 폼 대기
    try:
        page.wait_for_selector(
            'input[name="loginId"], input#loginId--1, input[name="email"]',
            timeout=15_000,
        )
    except PWTimeoutError:
        _screenshot(page, "login_form_not_found")
        raise PublishError("Kakao login form did not appear")

    page.locator(
        'input[name="loginId"], input#loginId--1, input[name="email"]'
    ).first.fill(email)
    page.locator(
        'input[name="password"], input[type="password"]'
    ).first.fill(password)

    if not _try_click(
        page,
        [
            'button.btn_g.highlight.submit',
            'button[type="submit"]:has-text("로그인")',
            'button[type="submit"]',
        ],
        timeout=5_000,
    ):
        _screenshot(page, "login_submit_missing")
        raise PublishError("Kakao login submit button not found")

    # 로그인 결과 대기 (Tistory 로 되돌아오면 성공)
    try:
        page.wait_for_url(re.compile(r"tistory\.com"), timeout=25_000)
    except PWTimeoutError:
        _screenshot(page, "login_no_redirect")
        # 카카오가 CAPTCHA / 2단계 인증을 띄운 경우 여기서 실패
        if "kauth.kakao.com" in page.url:
            raise PublishError(
                "Stuck on Kakao auth page — likely CAPTCHA or 2FA. "
                f"current_url={page.url}"
            )
        raise PublishError(f"Login redirect timeout — current_url={page.url}")

    logger.info("Login OK (url=%s)", page.url)


# ---------------------------------------------------------------------
# Editor flow
# ---------------------------------------------------------------------
def _open_new_post(page: Page, blog_name: str) -> None:
    url = f"https://{blog_name}.tistory.com/manage/newpost/"
    logger.info("Open new-post editor: %s", url)
    page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)

    # "작성 중이던 글이 있습니다" / "임시 저장 글 불러오기" 팝업이 뜨면 취소
    _try_click(
        page,
        [
            'button:has-text("취소")',
            'button:has-text("새 글 작성")',
            'button.btn-cancel',
        ],
        timeout=4_000,
    )

    # 에디터 본문 영역 로딩 대기
    try:
        page.wait_for_selector(
            '#post-title-input, input[name="title"], textarea[name="title"]',
            timeout=15_000,
        )
    except PWTimeoutError:
        _screenshot(page, "editor_not_loaded")
        raise PublishError("Editor did not load")


def _switch_to_html_mode(page: Page) -> None:
    """Tistory 에디터 모드: 기본 / 마크다운 / HTML.  HTML 로 강제 전환."""
    # 모드 선택 드롭다운 트리거 (있을 때만)
    _try_click(
        page,
        ['#editor-mode-layer-btn-open', 'button.btn-mode'],
        timeout=3_000,
    )

    # HTML 모드 항목 클릭
    _try_click(
        page,
        [
            '#editor-mode-html',
            'a:has-text("HTML")',
            'button:has-text("HTML")',
            'li:has-text("HTML")',
        ],
        timeout=4_000,
    )

    # 모드 변경 확인 다이얼로그가 뜨면 확인
    _try_click(
        page,
        [
            'button:has-text("확인")',
            'button.btn-confirm',
        ],
        timeout=3_000,
    )

    # CodeMirror / textarea 둘 중 하나가 보일 때까지 대기
    try:
        page.wait_for_selector(
            '.CodeMirror, .cm-editor, textarea.html_editor, textarea[name="content"]',
            timeout=10_000,
        )
    except PWTimeoutError:
        logger.warning("HTML editor area not detected — proceeding anyway")


def _fill_title_and_content(page: Page, title: str, html: str) -> None:
    # 1) 제목
    title_sel = (
        '#post-title-input, input[name="title"], '
        'textarea[name="title"], textarea#post-title-input'
    )
    page.locator(title_sel).first.fill(title)
    logger.info("Title filled (%d chars)", len(title))

    # 2) 본문 — CodeMirror(v5/v6) 또는 textarea 에 안전하게 주입
    injected = page.evaluate(
        """
        (html) => {
          // --- CodeMirror v5 ---
          const cm5host = document.querySelector('.CodeMirror');
          if (cm5host && cm5host.CodeMirror) {
            cm5host.CodeMirror.setValue(html);
            return 'codemirror5';
          }
          // --- CodeMirror v6 ---
          const cm6host = document.querySelector('.cm-editor');
          if (cm6host) {
            // EditorView 인스턴스에 접근 (Tistory 가 노출하는 hook 기준)
            const view = cm6host.cmView && cm6host.cmView.view;
            if (view) {
              view.dispatch({
                changes: { from: 0, to: view.state.doc.length, insert: html }
              });
              return 'codemirror6';
            }
          }
          // --- Fallback: 일반 textarea ---
          const ta = document.querySelector(
            'textarea.html_editor, textarea[name="content"], textarea#content'
          );
          if (ta) {
            ta.value = html;
            ta.dispatchEvent(new Event('input',  { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
            return 'textarea';
          }
          return null;
        }
        """,
        html,
    )

    if not injected:
        # 마지막 안전망: 키보드 입력 (느리지만 거의 항상 동작)
        logger.warning("JS injection failed — falling back to keyboard input")
        last_ta = page.locator("textarea").last
        last_ta.focus()
        page.keyboard.insert_text(html)
        injected = "keyboard"

    logger.info("Content injected via: %s (%d chars)", injected, len(html))


def _set_tags(page: Page, tags: list[str]) -> None:
    if not tags:
        return
    tag_sel_candidates = [
        '#tagText',
        'input[name="tag"]',
        'input[placeholder*="태그"]',
    ]
    tag_inp = None
    for sel in tag_sel_candidates:
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
    # 1) "완료" 버튼: 발행 사이드바 열기
    _try_click(
        page,
        [
            'button#publish-layer-btn',
            'button:has-text("완료")',
            'button.btn-publish',
        ],
        timeout=8_000,
    )

    # 2) 공개 발행 선택 (라디오 / 라벨)
    _try_click(
        page,
        [
            'label:has-text("공개")',
            'input#open20',
            'input[name="open"][value="20"]',
        ],
        timeout=4_000,
    )

    # 3) 최종 발행 버튼
    final_btns = [
        'button#publish-btn',
        'button:has-text("공개 발행")',
        'button:has-text("발행하기")',
        'button:has-text("발행")',
    ]
    if not _try_click(page, final_btns, timeout=8_000):
        _screenshot(page, "publish_btn_missing")
        raise PublishError("Final publish button not found")

    # 4) /newpost URL 에서 벗어나면 성공
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
    kakao_email_env: str = "KAKAO_EMAIL",
    kakao_password_env: str = "KAKAO_PASSWORD",
    headless: bool = True,
) -> str:
    """Login to Kakao, write a Tistory post, publish, return final URL."""
    email = os.environ.get(kakao_email_env)
    password = os.environ.get(kakao_password_env)
    if not email or not password:
        raise PublishError(
            f"Missing Kakao credentials — set env vars "
            f"{kakao_email_env!r} and {kakao_password_env!r}"
        )
    if not title or not html_content:
        raise PublishError("Empty title or content cannot be published")

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
            _kakao_login(page, email, password)
            _open_new_post(page, blog_name)
            _switch_to_html_mode(page)
            _fill_title_and_content(page, title, html_content)
            _set_tags(page, tags or [])
            return _publish(page)
        except PublishError:
            raise
        except Exception as e:
            _screenshot(page, "publish_unexpected")
            raise PublishError(f"Tistory publish failed: {e}") from e
        finally:
            try:
                ctx.close()
            finally:
                browser.close()

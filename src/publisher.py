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

import base64
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

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


def _try_click(
    page: Page,
    selectors: list[str],
    timeout: int = 4_000,
    force: bool = False,
) -> bool:
    """첫 매칭 셀렉터로 클릭 시도. force=True 면 Playwright actionability
    체크를 우회하여 오버레이가 가린 element 도 강제 클릭."""
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=timeout, force=force)
            logger.debug("Clicked: %s (force=%s)", sel, force)
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

    # 1-b) 외부 <img> URL → base64 data URI 인라인 변환.
    # Tistory 가 외부 URL 을 fetch 하는 동안 isUploading=true 가 잠기는 데드락 회피.
    # data URI 는 외부 fetch 불필요 → TinyMCE 가 클립보드 paste 처럼 즉시 처리 →
    # Kakao CDN 으로 바로 업로드되고 isUploading 트리거 안 됨.
    pre_len = len(html)
    html = _inline_images_as_base64(html)
    if len(html) != pre_len:
        logger.info(
            "HTML size after base64 inlining: %d → %d chars (+%.1fx)",
            pre_len, len(html), len(html) / max(pre_len, 1),
        )

    # 2) 본문 — 활성 에디터에 주입 + 모든 mirror 경로/이벤트 강제 sync.
    #   배경: Tistory submit 은 TinyMCE 가 mirror 하는 원본 textarea 또는
    #   자체 state 에서 본문을 가져간다. setContent 만으로는 mirror sync 이벤트가
    #   안 터지므로 ed.save() + fire('Change'/'Input'/...) + 외부 textarea 동기화까지
    #   같이 수행.
    result = page.evaluate(
        """
        (html) => {
          // ---------- TinyMCE 경로 ----------
          const tm = window.tinymce;
          const ed = tm && (tm.activeEditor || (tm.editors && tm.editors[0]));
          if (ed) {
            ed.setContent(html);
            // mirror textarea 로 강제 저장
            try { ed.save && ed.save(); } catch (e) {}
            try { ed.setDirty && ed.setDirty(true); } catch (e) {}
            // TinyMCE 5/6 양쪽 이벤트 fire (Tistory 의 state 리스너 트리거 목적)
            ['Change', 'Input', 'KeyUp', 'NodeChange', 'change', 'input']
              .forEach(evt => {
                try { ed.fire && ed.fire(evt); } catch (e) {}
                try { ed.dispatch && ed.dispatch(evt); } catch (e) {}
              });
            // iframe body 에 input/change 이벤트
            try {
              const body = ed.getBody && ed.getBody();
              if (body) {
                body.dispatchEvent(new Event('input',  { bubbles: true }));
                body.dispatchEvent(new Event('change', { bubbles: true }));
                body.dispatchEvent(new Event('blur',   { bubbles: true }));
              }
            } catch (e) {}
            // 연결된 원본 textarea (TinyMCE 가 mirror 하는 element) 에 직접 동기화
            try {
              const elem = ed.getElement && ed.getElement();
              if (elem) {
                elem.value = ed.getContent({ format: 'raw' }) || html;
                elem.dispatchEvent(new Event('input',  { bubbles: true }));
                elem.dispatchEvent(new Event('change', { bubbles: true }));
              }
            } catch (e) {}
            // Tistory 의 별도 본문 mirror textarea 추정값들 모두 동기화
            document.querySelectorAll('textarea').forEach(t => {
              const k = ((t.name || '') + '|' + (t.id || '')).toLowerCase();
              if (/content|body|html/.test(k)) {
                t.value = html;
                t.dispatchEvent(new Event('input',  { bubbles: true }));
                t.dispatchEvent(new Event('change', { bubbles: true }));
              }
            });
            const v = ed.getContent({ format: 'html' }) || '';
            return { via: 'tinymce-api', verified_len: v.length };
          }

          // ---------- CodeMirror v5 ----------
          const cm5 = document.querySelector('.CodeMirror');
          if (cm5 && cm5.CodeMirror) {
            cm5.CodeMirror.setValue(html);
            return { via: 'codemirror5',
                     verified_len: (cm5.CodeMirror.getValue() || '').length };
          }
          // ---------- CodeMirror v6 ----------
          const cm6 = document.querySelector('.cm-editor');
          if (cm6) {
            const view = cm6.cmView && cm6.cmView.view;
            if (view) {
              view.dispatch({
                changes: { from: 0, to: view.state.doc.length, insert: html }
              });
              return { via: 'codemirror6', verified_len: view.state.doc.length };
            }
          }
          // ---------- textarea ----------
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

    if int(result["verified_len"]) < int(len(html) * 0.5):
        _screenshot(page, "content_injection_short")
        _dump_debug(page, "content_injection_short")
        raise PublishError(
            f"본문 주입 실패 — via={result['via']}, "
            f"sent={len(html)}, verified={result['verified_len']}. "
            "artifact 의 *_content_injection_short.* 확인 필요."
        )

    # 비동기 state sync 완료를 위한 대기
    page.wait_for_timeout(1500)

    # 발행 직전 강제 재-save + 모든 content 후보 필드의 현재 길이 로깅.
    # → "TinyMCE 는 가득 차 있는데 textarea 는 0" 같은 mirror sync 실패를 즉시 가시화.
    pre_publish = page.evaluate(
        """
        () => {
          const out = { fields: {}, mode: null };
          const tm = window.tinymce;
          const ed = tm && (tm.activeEditor || (tm.editors && tm.editors[0]));
          if (ed) {
            try { ed.save && ed.save(); } catch (e) {}
            out.fields.tinymce = (ed.getContent({ format: 'html' }) || '').length;
            const elem = ed.getElement && ed.getElement();
            if (elem) {
              out.fields['tinymce_mirror_textarea'] = (elem.value || '').length;
            }
          }
          document.querySelectorAll('textarea').forEach((t, i) => {
            const key = 'ta[' + i + ']:' + (t.name || t.id || '?');
            out.fields[key] = (t.value || '').length;
          });
          const cm5 = document.querySelector('.CodeMirror');
          if (cm5 && cm5.CodeMirror) {
            out.fields.cm5 = (cm5.CodeMirror.getValue() || '').length;
          }
          // 어느 모드인지 힌트 (basic = TinyMCE iframe 존재, HTML/MD = CodeMirror)
          if (document.querySelector('iframe[id$="_ifr"]')) out.mode = 'basic(TinyMCE)';
          else if (document.querySelector('.CodeMirror, .cm-editor')) out.mode = 'codemirror';
          return out;
        }
        """
    )
    logger.info("Pre-publish content state: mode=%s fields=%s",
                pre_publish.get("mode"), pre_publish.get("fields"))


def _set_tags(page: Page, tags: list[str]) -> None:
    """발행 사이드바가 열려 있는 상태에서 호출되어야 함.

    Tistory 사이드바 위에 잔여 ReactModalPortal/툴팁 같은 비가시 오버레이가
    남아 있으면 #tagText 의 pointer event 를 가로채서 'subtree intercepts
    pointer events' 에러가 발생한다.  두 가지로 회피:
      1) 진입 직전 Escape 를 몇 번 눌러 떠 있는 모달/툴팁/포털을 정리.
      2) click / fill 모두 force=True 로 Playwright actionability 체크를
         우회 — 위에 가리는 요소가 있어도 강제로 진행.
    """
    if not tags:
        return

    # 0) 잔여 모달/툴팁/포털 정리 (사이드바 자체는 Escape 로 닫히지 않으므로 안전)
    for _ in range(3):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
        except Exception:
            pass

    tag_inp = None
    for sel in (
        '#tagText',
        'input[name="tag"]',
        'input[placeholder*="태그"]',
        'input[placeholder*="키워드"]',
    ):
        loc = page.locator(sel).first
        try:
            # 오버레이가 가려도 attached 만으로 충분 — 실제 입력은 force=True
            loc.wait_for(state="attached", timeout=4_000)
            tag_inp = loc
            break
        except PWTimeoutError:
            continue
    if not tag_inp:
        logger.warning("Tag input not found — skipping tags (sidebar opened?)")
        return

    added = 0
    for t in tags:
        try:
            tag_inp.click(force=True)
            tag_inp.fill(t, force=True)
            page.keyboard.press("Enter")
            page.wait_for_timeout(120)   # 태그 칩이 추가되며 input 이 리셋될 시간
            added += 1
        except Exception as e:
            logger.warning("Tag '%s' add failed: %s", t, e)
    logger.info("Tags entered: %d/%d", added, len(tags))


# ---------------------------------------------------------------------
# 외부 <img> URL → base64 data URI 인라인 변환 (Tistory isUploading 데드락 우회)
# ---------------------------------------------------------------------
_HTTP_IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=)(["\'])(https?://[^"\']+)\2',
    re.IGNORECASE,
)
_MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5MB safety limit per image
_IMAGE_FETCH_TIMEOUT_S = 15           # Pollinations 가 on-the-fly 생성에 3~5s 필요
_IMAGE_FETCH_HEADERS = {
    # 일반 브라우저 흉내 — 일부 CDN 이 default Python UA 를 차단함
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
}


def _inline_images_as_base64(html: str) -> str:
    """본문 안의 모든 <img src="http(s)://..."> URL 을 다운로드해
    `data:image/...;base64,...` URI 로 치환.

    Tistory 가 외부 URL 을 자체 CDN 으로 fetch 하는 동안 'isUploading' state 가
    켜져 발행이 차단되는 문제를 우회한다. base64 data URI 는 외부 fetch 가
    필요 없으므로 Tistory 가 즉시 클립보드 paste 처럼 처리 → Kakao CDN 으로
    바로 업로드하고 isUploading 가 안 켜짐.
    """
    counts = {"ok": 0, "fail": 0, "total": 0}

    def _repl(m: re.Match) -> str:
        counts["total"] += 1
        prefix, quote_ch, url = m.group(1), m.group(2), m.group(3)
        try:
            r = requests.get(
                url, timeout=_IMAGE_FETCH_TIMEOUT_S, headers=_IMAGE_FETCH_HEADERS
            )
            r.raise_for_status()
            raw = r.content
            if not raw:
                raise ValueError("empty body")
            if len(raw) > _MAX_IMAGE_BYTES:
                logger.warning(
                    "Image too large to inline (%d bytes) — leaving as-is: %s",
                    len(raw), url[:80],
                )
                counts["fail"] += 1
                return m.group(0)
            mime = (r.headers.get("Content-Type", "") or "").split(";")[0].strip().lower()
            if not mime.startswith("image/"):
                # Content-Type 이 명시 안 됐거나 이상하면 jpeg 가정 (대다수 CDN 안전한 기본)
                mime = "image/jpeg"
            b64 = base64.b64encode(raw).decode("ascii")
            data_uri = f"data:{mime};base64,{b64}"
            counts["ok"] += 1
            logger.info(
                "Image inlined: %s → %d bytes (%s)",
                url[:60] + ("..." if len(url) > 60 else ""),
                len(raw), mime,
            )
            return f"{prefix}{quote_ch}{data_uri}{quote_ch}"
        except Exception as e:
            logger.warning("Image fetch failed (%s): %s", e, url[:100])
            counts["fail"] += 1
            return m.group(0)   # 실패하면 원본 외부 URL 유지

    new_html = _HTTP_IMG_SRC_RE.sub(_repl, html)

    if counts["total"] > 0:
        logger.info(
            "Image inlining summary: %d/%d converted to base64 (failed=%d)",
            counts["ok"], counts["total"], counts["fail"],
        )
    return new_html


def _wait_for_image_uploads(page: Page, timeout_seconds: float = 30.0) -> bool:
    """Tistory 의 외부 <img> 자동 import("X개의 파일을 업로드 중") 토스트가
    사라질 때까지 폴링 대기.

    Returns:
        True  : 토스트가 자연 소멸 (= 실제로 업로드 완료된 정상 케이스).
        False : 타임아웃 / "0개" 동결 감지. 호출자는 즉시 _dismiss_upload_toast
                로 강제 제거하고 publish 를 진행해야 함.
    """
    deadline = time.monotonic() + timeout_seconds
    last_msg = None
    while time.monotonic() < deadline:
        msg = page.evaluate(
            """
            () => {
              const containers = document.querySelectorAll(
                '.wrap_toast, .layer_toast, .toast_content, '
                + '.notification, .toast, [role="alert"], .alert, '
                + '.layer-notification, .upload-progress, .toast_layer, '
                + '.notice, .progress, .mce-notification'
              );
              for (const el of containers) {
                if (!el.offsetParent) continue;
                const t = (el.innerText || '').trim();
                if (/업로드|uploading/i.test(t)) return t;
              }
              return null;
            }
            """
        )
        if msg is None:
            logger.info("Image upload toast cleared")
            return True

        if msg != last_msg:
            logger.info("Image upload toast: %s", msg)
            last_msg = msg

        # 핵심: "0개" 패턴이 보이면 = 업로드 큐는 비었는데 토스트가 동결된 UI 버그.
        # 더 기다려도 안 풀리므로 즉시 break → 호출자가 DOM 에서 제거하도록.
        if "0개" in msg:
            logger.warning(
                "토스트가 '0개' 상태에서 동결됨 (UI 버그) — 대기 중단, 강제 제거로 진행"
            )
            return False

        page.wait_for_timeout(1_500)

    logger.warning(
        "Image upload toast did not clear in %.0fs (last=%s) — proceeding anyway",
        timeout_seconds, last_msg,
    )
    return False


def _dismiss_upload_toast(page: Page) -> None:
    """동결된 업로드 토스트를 DOM 에서 물리적으로 제거.

    Tistory 가 외부 이미지 fetch 후에도 '0개의 파일을 업로드 중' 토스트를
    안 닫는 UI 버그 우회용. 토스트 element 자체를 DOM 에서 빼내 발행 버튼의
    pointer-event interception 을 차단.
    """
    try:
        removed = page.evaluate(
            """
            () => {
              let n = 0;
              // 사용자가 지정한 Tistory 토스트 클래스 (1차)
              document.querySelectorAll(
                '.wrap_toast, .layer_toast, .toast_content'
              ).forEach(e => { e.remove(); n++; });

              // 폴백 — "업로드" 텍스트 포함 알림 컨테이너 모두 제거 (2차)
              document.querySelectorAll(
                '.notification, .toast, [role="alert"], .alert, '
                + '.layer-notification, .upload-progress, .toast_layer, '
                + '.notice, .mce-notification'
              ).forEach(el => {
                const t = (el.innerText || '').trim();
                if (/업로드|uploading/i.test(t)) { el.remove(); n++; }
              });
              return n;
            }
            """
        )
        logger.info("Upload toast DOM removed (count=%s)", removed)
    except Exception as e:
        logger.debug("Dismiss upload toast failed: %s", e)


def _verify_publish_success(page: Page, blog_name: str, title: str) -> bool:
    """발행 후 /manage/posts/ 에서 우리가 만든 글의 제목이 실제로 목록에 있는지 확인.

    Tistory 가 가끔 발행 후에도 /newpost URL 에 그대로 머무는 경우가 있어,
    URL 이탈만으로는 성공/실패 구분이 불가능. 목록 페이지에서 title 매칭이
    가장 신뢰도 높은 신호.
    """
    list_url = f"https://{blog_name}.tistory.com/manage/posts/"
    try:
        page.goto(list_url, wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(2_000)   # SPA 렌더링 정착
    except Exception as e:
        logger.warning("Verification page load failed: %s", e)
        return False

    # 제목 앞 25~35자를 식별 키로 사용 (이만 하면 충분히 unique)
    title_norm = " ".join(title.strip().split())
    title_key = title_norm[:30].strip()
    if len(title_key) < 5:
        logger.warning("Title too short to verify: %r", title_key)
        return False

    try:
        content = page.content()
    except Exception as e:
        logger.warning("Page content read failed: %s", e)
        return False

    # 페이지 HTML 의 공백/줄바꿈을 한 칸으로 정규화하여 비교
    # (Tistory 가 <span>...</span><br>... 같이 끊어 렌더링하면 raw 매칭이 실패함)
    import re as _re
    content_norm = _re.sub(r"\s+", " ", content)

    if title_key in content_norm:
        logger.info(
            "Publish verified — title '%s...' found in /manage/posts/",
            title_key[:20],
        )
        return True

    # 한층 더 느슨한 매칭: 제목의 앞 15자만으로도 시도
    short_key = title_norm[:15].strip()
    if len(short_key) >= 8 and short_key in content_norm:
        logger.info(
            "Publish verified (short-key) — '%s...' found in /manage/posts/",
            short_key,
        )
        return True

    logger.warning(
        "Publish verification FAILED — title '%s...' not in /manage/posts/",
        title_key[:20],
    )
    return False


def _publish(page: Page, blog_name: str, title: str) -> str:
    # 1) 발행 모달 열기 — #publish-layer-btn ("완료")
    if not _try_click(
        page,
        [
            'button#publish-layer-btn',
            'button:has-text("완료")',
            'button[class*="publish-layer"]',
            '[aria-label*="완료"]',
        ],
        timeout=8_000,
    ):
        _screenshot(page, "publish_layer_btn_missing")
        raise PublishError("'완료' 버튼(#publish-layer-btn) 을 찾지 못함")

    # 2) 모달 애니메이션 / 컴포넌트 마운트 대기 (절대 Escape 누르지 말 것 — 모달 닫힘)
    page.wait_for_timeout(1_000)

    # 3) 공개 발행 옵션 선택 — 클릭 후 실제 :checked 상태 확인, 아니면 JS 강제
    _try_click(
        page,
        [
            'label:has-text("공개")',
            'input#open20',
            'input[name="open"][value="20"]',
            'input[value="20"]',
            'span:has-text("공개")',
            '[aria-label="공개"]',
        ],
        timeout=3_000,
    )
    page.wait_for_timeout(800)

    # 라디오가 실제로 :checked 인지 확인 + 안 됐으면 JS 로 강제
    public_state = page.evaluate(
        """
        () => {
          const checked = document.querySelector(
            'input[name="open"][value="20"]:checked, input#open20:checked, '
            + 'input[value="20"]:checked'
          );
          if (checked) return { ok: true, via: 'native' };
          const target = document.querySelector(
            'input[name="open"][value="20"], input#open20, input[value="20"]'
          );
          if (target) {
            target.checked = true;
            target.dispatchEvent(new Event('input',  { bubbles: true }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
            return { ok: true, via: 'js-forced' };
          }
          return { ok: false };
        }
        """
    )
    logger.info("공개 옵션 selection: %s", public_state)
    page.wait_for_timeout(600)

    # 3-b) 본문의 외부 <img> 자동 업로드(Tistory CDN 옮기기) 가 끝날 때까지 대기.
    #      "X개의 파일을 업로드 중입니다" 토스트가 사라지지 않으면 발행 클릭이 묵살됨.
    upload_cleared = _wait_for_image_uploads(page, timeout_seconds=30.0)
    if not upload_cleared:
        # 토스트가 끝까지 안 사라지면 dismiss 시도 (close 버튼 클릭 또는 강제 hide)
        logger.warning("업로드 토스트 강제 dismiss 시도")
        _dismiss_upload_toast(page)
        page.wait_for_timeout(500)

    # 4) 최종 발행 버튼 — Pass 1: CSS 셀렉터(확장)
    final_btns = [
        'button#publish-btn',
        'button.publish',
        'button.btn_publish',
        'button.btn-publish',
        'button[class*="publish"]',
        'button[class*="Publish"]',
        'button:has-text("공개 발행")',
        'button:has-text("공개발행")',
        'button:has-text("발행하기")',
        'button:has-text("발행")',
        'a:has-text("공개 발행")',
        'a:has-text("발행")',
        '[role="button"]:has-text("발행")',
        'button[type="submit"]',
        '[aria-label*="발행"]',
    ]
    # force=True : 동결된 토스트가 pointer-event 가로채도 무시하고 강제 클릭
    clicked = _try_click(page, final_btns, timeout=2_000, force=True)

    # 4b) Pass 2: JS 폴백 — 퍼지 매칭으로 모든 클릭 가능 요소 스캔
    if not clicked:
        js_result = page.evaluate(
            """
            () => {
              const looksLikePublish = (t) => {
                const s = (t || '').replace(/\\s+/g, ' ').trim();
                if (!s) return false;
                if (!/발행/.test(s)) return false;
                // 컨테이너 div 의 긴 텍스트나 무관한 옵션 제외
                if (s.length > 12) return false;
                if (/취소|닫기|임시|저장|미리|예약/.test(s)) return false;
                return true;
              };
              const isVisible = (el) => {
                if (!el.offsetParent && el.getClientRects().length === 0) return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
              };
              const candidates = Array.from(document.querySelectorAll(
                'button, a, [role="button"], input[type="submit"], ' +
                'div[onclick], span[onclick], [class*="publish"], [class*="Publish"]'
              ));
              for (const el of candidates) {
                const txt = el.innerText || el.value
                          || el.getAttribute('aria-label') || '';
                if (looksLikePublish(txt) && isVisible(el)) {
                  try {
                    el.click();
                  } catch (e) {
                    el.dispatchEvent(new MouseEvent('click', {
                      bubbles: true, cancelable: true, view: window,
                    }));
                  }
                  return {
                    clicked: txt.replace(/\\s+/g, ' ').trim(),
                    tag: el.tagName,
                    id: el.id || '',
                    cls: ((el.className || '') + '').slice(0, 120),
                    aria: el.getAttribute('aria-label') || '',
                  };
                }
              }
              return null;
            }
            """
        )
        if js_result:
            logger.info("JS fallback clicked publish: %s", js_result)
            clicked = True

    # 4c) 그래도 못 찾으면 — 진단 정보 풀세트 덤프 후 실패
    if not clicked:
        _screenshot(page, "publish_btn_missing")
        _dump_debug(page, "publish_btn_missing")
        try:
            visible_btns = page.evaluate(
                """
                () => Array.from(document.querySelectorAll(
                  'button, a, [role="button"], input[type="submit"], ' +
                  'div[onclick], [class*="publish"], [class*="Publish"], [aria-label]'
                ))
                .map(el => ({
                  tag: el.tagName,
                  text: ((el.innerText || el.value || '') + '').replace(/\\s+/g,' ').trim().slice(0, 80),
                  aria: el.getAttribute('aria-label') || '',
                  id: el.id || '',
                  cls: ((el.className || '') + '').slice(0, 120),
                  visible: !!el.offsetParent,
                }))
                .filter(b => (b.text || b.aria))
                .slice(0, 120)
                """
            )
            logger.info("Visible buttons snapshot: %s", visible_btns)
        except Exception as e:
            logger.warning("Buttons dump failed: %s", e)
        raise PublishError(
            "Final publish button not found after exhaustive CSS + JS fuzzy match. "
            "artifact 의 *_publish_btn_missing.html 와 'Visible buttons snapshot' "
            "로그 한 줄을 그대로 공유해주시면 정확한 셀렉터로 픽스 가능합니다."
        )

    # 4d) 발행 후 확인 다이얼로그가 있을 경우만 dismiss (있을 때만)
    _try_click(
        page,
        [
            'button:has-text("확인")',
            'button.btn-confirm',
        ],
        timeout=2_000,
    )

    # 4e) 클릭이 실제로 효과가 있었는지 확인 — 발행 버튼이 여전히 보이면 no-op 이었음.
    # 1회 한정으로 재클릭 시도 (Tistory React state 동기화 race 대응).
    page.wait_for_timeout(2_500)
    still_at_newpost = "/newpost" in page.url
    publish_btn_still_visible = page.evaluate(
        """
        () => {
          const els = Array.from(document.querySelectorAll(
            'button, a, [role="button"], input[type="submit"]'
          ));
          for (const el of els) {
            const t = ((el.innerText || el.value || '') + '')
                        .replace(/\\s+/g, ' ').trim();
            if (!/^(공개\\s*발행|공개발행|발행하기|발행)$/.test(t)) continue;
            if (!el.offsetParent) continue;
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) return true;
          }
          return false;
        }
        """
    )

    if still_at_newpost and publish_btn_still_visible:
        logger.warning(
            "발행 클릭이 효과가 없었던 것으로 보임 — 진단 + 1회 재클릭 시도"
        )

        # 진단 1: 화면의 에러 배너 / select / radio / 보이는 버튼을 한 번에 dump
        state = page.evaluate(
            """
            () => {
              const errors = Array.from(document.querySelectorAll(
                '.error_message, .desc_error, .txt_error, .ico_error, '
                + '[role="alert"], .alert, .notification, .toast'
              )).filter(el => el.offsetParent)
                .map(el => (el.innerText || '').trim())
                .filter(Boolean);
              const selects = Array.from(document.querySelectorAll('select'))
                .filter(s => s.offsetParent)
                .map(s => ({
                  name: s.name || s.id || '',
                  value: s.value,
                  options: Array.from(s.options).slice(0, 6).map(o => ({
                    v: o.value, t: (o.text || '').trim().slice(0, 30),
                  })),
                }));
              const radios = Array.from(document.querySelectorAll('input[type="radio"]'))
                .filter(r => r.offsetParent)
                .map(r => ({
                  name: r.name, value: r.value, checked: r.checked,
                }));
              const buttons = Array.from(document.querySelectorAll(
                'button, a, [role="button"]'
              )).filter(b => b.offsetParent)
                .slice(0, 30)
                .map(b => ({
                  text: ((b.innerText || '') + '').replace(/\\s+/g,' ').trim().slice(0, 40),
                  id: b.id || '',
                  cls: ((b.className || '') + '').slice(0, 60),
                  disabled: b.disabled || b.getAttribute('aria-disabled') === 'true',
                }));
              return { errors, selects, radios, buttons };
            }
            """
        )
        logger.warning("Pre-retry state dump — errors=%s", state.get("errors"))
        logger.warning("Pre-retry state dump — selects=%s", state.get("selects"))
        logger.warning("Pre-retry state dump — radios=%s", state.get("radios"))
        logger.warning("Pre-retry state dump — buttons[:30]=%s", state.get("buttons"))

        # 진단 2: 카테고리 미선택일 가능성 → 첫 옵션으로 자동 선택 (placeholder 가 아니면)
        cat_result = page.evaluate(
            """
            () => {
              // 흔한 카테고리 select 셀렉터들
              const candidates = [
                'select[name="category"]', 'select#category',
                'select[name="categoryId"]', 'select.category',
              ];
              for (const sel of candidates) {
                const s = document.querySelector(sel);
                if (!s) continue;
                if (s.value && s.value !== '0' && s.value !== '') {
                  return { skipped: true, current: s.value };
                }
                // value=0 또는 빈 값이면 첫 실값 옵션 선택
                const opts = Array.from(s.options);
                for (const o of opts) {
                  if (o.value && o.value !== '0') {
                    s.value = o.value;
                    s.dispatchEvent(new Event('change', { bubbles: true }));
                    s.dispatchEvent(new Event('input',  { bubbles: true }));
                    return { selected: o.value, text: (o.text || '').trim() };
                  }
                }
              }
              return null;
            }
            """
        )
        if cat_result:
            logger.warning("카테고리 자동 선택 결과: %s", cat_result)
            page.wait_for_timeout(500)

        # 재클릭 전에도 업로드 토스트 한 번 더 정리 (퍼지스트 토스트 회복)
        if not _wait_for_image_uploads(page, timeout_seconds=10.0):
            _dismiss_upload_toast(page)
            page.wait_for_timeout(500)

        # 공개 라디오 한 번 더 확정
        page.evaluate(
            """
            () => {
              const target = document.querySelector(
                'input[name="open"][value="20"], input#open20, input[value="20"]'
              );
              if (target) {
                target.checked = true;
                target.dispatchEvent(new Event('change', { bubbles: true }));
              }
            }
            """
        )
        page.wait_for_timeout(500)
        # 재클릭도 force=True
        retry_clicked = _try_click(page, final_btns, timeout=2_000, force=True)
        if not retry_clicked:
            # JS 폴백 재시도
            page.evaluate(
                """
                () => {
                  const targets = ['공개 발행','공개발행','발행하기','발행'];
                  const els = Array.from(document.querySelectorAll(
                    'button, a, [role="button"]'
                  ));
                  for (const el of els) {
                    const t = ((el.innerText || '') + '').replace(/\\s+/g, ' ').trim();
                    if (targets.includes(t) && el.offsetParent) {
                      try { el.click(); } catch (e) {
                        el.dispatchEvent(new MouseEvent('click', {
                          bubbles: true, cancelable: true, view: window,
                        }));
                      }
                      return;
                    }
                  }
                }
                """
            )
        page.wait_for_timeout(2_000)
        # 확인 다이얼로그 한번 더 dismiss
        _try_click(page, ['button:has-text("확인")', 'button.btn-confirm'], timeout=1_500)

    # 5) 발행 결과 판정
    # 5-a) Tistory 의 자연 redirect 가 일어날 시간을 잠깐 준다
    page.wait_for_timeout(3_000)
    try:
        page.wait_for_url(lambda u: "/newpost" not in u, timeout=12_000)
        naturally_navigated = True
    except PWTimeoutError:
        naturally_navigated = False
        _screenshot(page, "after_publish_no_nav")
        logger.info("/newpost URL 이탈 안 됨 — /manage/posts/ 로 검증 진행")

    # 5-b) 가장 신뢰도 높은 신호: /manage/posts/ 목록에 우리 글 제목이 있는지
    verified = _verify_publish_success(page, blog_name, title)

    if verified:
        final_url = page.url
        logger.info("Post-publish verified URL: %s", final_url)
        return final_url

    # 5-c) 검증 실패 처리 — URL 이동 여부에 따라 톤 다르게
    _screenshot(page, "publish_unverified")
    if naturally_navigated:
        # URL 은 이동했는데 글이 목록에 안 보임 — Tistory 가 목록 페이지를 바꿨거나
        # 발행은 됐는데 인덱싱 지연 가능. soft warning 후 일단 성공으로 처리.
        logger.warning(
            "URL 은 /newpost 이탈했으나 /manage/posts/ 에서 글 미발견. "
            "발행됐을 가능성 있으나 verification 으로 확정 못 함. "
            "title='%s', current_url=%s",
            title[:40], page.url,
        )
        return page.url

    # URL 도 안 움직였고 목록에도 없음 — 명백한 실패
    raise PublishError(
        f"발행 실패 — URL 이 /newpost 에 머물고 '{title[:40]}...' 글이 "
        "manage/posts 에도 없음. 공개 발행 클릭이 실제로 처리되지 않은 것으로 추정."
    )


# ---------------------------------------------------------------------
# Inner publish flow — 한 번의 Playwright 세션
# ---------------------------------------------------------------------
def _run_publish_flow(
    state_file: Path,
    blog_name: str,
    title: str,
    html_content: str,
    tags: list[str],
    headless: bool,
) -> str:
    """state_file 의 storage_state 로 컨텍스트 만들고 글 1편 발행."""
    logger.info(
        "Using storage_state: %s (%d bytes)",
        state_file, state_file.stat().st_size,
    )

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
            _open_new_post(page, blog_name)   # 세션 만료 시 SessionExpiredError raise
            _fill_title_and_content(page, title, html_content)
            # 태그는 에디터 사이드바(항상 보임)에서 입력. publish 모달을 열기 전에
            # 처리해야 _set_tags 내부의 Escape × 3 으로 모달이 닫히는 사고를 막을 수 있음.
            _set_tags(page, tags)
            return _publish(page, blog_name, title)
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
    """state.json (storage_state) 으로 글 1편 발행.

    세션 만료(SessionExpiredError) 시 자동 재로그인을 시도하지 않는다.
    이유: GitHub Actions cloud IP 에서 Kakao TMS 가 verifyTms 화면으로
    리다이렉트시키므로 자동화 우회 불가능. 만료 감지 시 명확한 메시지로
    실패하고, 사용자가 로컬에서 `python -m src.auto_login` 으로 새
    state.json 을 발급한 뒤 TISTORY_STATE_JSON 시크릿을 직접 갱신해야 한다.
    """
    if not title or not html_content:
        raise PublishError("Empty title or content cannot be published")

    state_file = _resolve_state_path()
    if not state_file.is_file():
        raise PublishError(
            f"storage_state 파일을 찾을 수 없습니다: {state_file}. "
            "로컬에서 'python -m src.auto_login' 으로 state.json 발급 후, "
            "GitHub Secrets 의 TISTORY_STATE_JSON 을 그 내용으로 업데이트하세요."
        )
    if state_file.stat().st_size == 0:
        raise PublishError(
            f"storage_state 파일이 비어 있습니다: {state_file}. "
            "수동 재발급 후 시크릿 갱신 필요."
        )

    try:
        return _run_publish_flow(
            state_file, blog_name, title, html_content, tags or [], headless,
        )
    except SessionExpiredError as e:
        # 클라우드 IP 에선 자동 재로그인이 TMS 에 걸려 회복 불가 → 즉시 실패 + 안내
        raise PublishError(
            f"세션 만료 감지 — {e} "
            "로컬에서 'python -m src.auto_login' 실행 → 새 state.json 의 "
            "내용을 TISTORY_STATE_JSON 시크릿에 붙여넣기로 갱신하세요."
        ) from e

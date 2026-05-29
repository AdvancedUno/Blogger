"""Tistory storage_state 자동 재발급 (Self-Healing).

publisher 가 SessionExpiredError 를 던졌을 때 호출되어, Kakao 계정으로
다시 로그인하고 새 state.json 을 저장한다.

⚠️ 운영 시 알아둘 점
  - Kakao 가 CAPTCHA / 2단계 인증을 띄우면 자동화 불가. 그 경우 수동
    state.json 재발급이 필요하고 본 함수는 명확한 AutoLoginError 로 종료.
  - GitHub Actions runner IP 는 클라우드 대역이라 CAPTCHA 가 뜰 위험이
    상존한다. 자동화 전용 Kakao 계정에서는 2FA 를 끄고, 가능하면 평소
    storage_state 재발급을 자주 해 IP 신뢰도가 높은 상태로 유지.
  - 자격증명은 환경변수 KAKAO_EMAIL / KAKAO_PASSWORD 로 주입.
  - 인간 같은 타이핑 (keystroke delay) 으로 기본적인 봇 탐지를 회피.
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


class AutoLoginError(RuntimeError):
    """Raised when the auto-login flow fails."""


DEFAULT_STATE_PATH = "state.json"
DEFAULT_TIMEOUT_MS = 30_000
TYPING_DELAY_MS = 100   # 키 입력당 100ms — 인간 같은 속도로 봇 탐지 우회
LOGIN_DEADLINE_S = 30.0


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _try_click(page: Page, selectors: list[str], timeout: int = 4_000) -> bool:
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=timeout)
            return True
        except PWTimeoutError:
            continue
        except Exception as e:
            logger.debug("Click '%s' err: %s", sel, e)
    return False


def _human_type(page: Page, locator, text: str) -> None:
    """포커스를 잡고 키보드로 한 글자씩 typing — fill 보다 봇 탐지에 강함."""
    locator.click()
    page.keyboard.type(text, delay=TYPING_DELAY_MS)


# ---------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------
def renew_tistory_session(
    state_path: str | Path = DEFAULT_STATE_PATH,
    headless: bool = True,
    email_env: str = "KAKAO_EMAIL",
    password_env: str = "KAKAO_PASSWORD",
) -> Path:
    """Kakao 계정으로 로그인하고 storage_state 를 `state_path` 에 저장.

    Returns:
        저장된 state.json 의 절대 경로.

    Raises:
        AutoLoginError: 환경변수 누락, 셀렉터 실패, Kakao 자격증명 거부,
            CAPTCHA/2FA 노출, 리다이렉트 타임아웃 등.
    """
    email = os.environ.get(email_env)
    password = os.environ.get(password_env)
    if not email or not password:
        raise AutoLoginError(
            f"환경변수 {email_env!r} / {password_env!r} 가 설정되지 않음 — "
            "자동 로그인 불가."
        )

    state_file = Path(state_path)
    if not state_file.is_absolute():
        state_file = Path.cwd() / state_file

    logger.info("Auto-login: starting Kakao login flow (state → %s)", state_file)

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
            # 1) Tistory 로그인 페이지 진입
            logger.info("Auto-login: → tistory.com/auth/login")
            page.goto(
                "https://www.tistory.com/auth/login",
                wait_until="domcontentloaded",
                timeout=DEFAULT_TIMEOUT_MS,
            )

            # 2) "카카오계정으로 로그인" 클릭
            if not _try_click(
                page,
                [
                    'a:has-text("카카오계정으로 로그인")',
                    'a.btn_login.link_kakao_id',
                    'a[href*="kauth.kakao.com"]',
                ],
                timeout=6_000,
            ):
                raise AutoLoginError("'카카오계정으로 로그인' 버튼을 찾지 못함")

            # 3) Kakao 로그인 폼 대기
            try:
                page.wait_for_selector(
                    'input[name="loginId"], input#loginId--1, input[name="email"]',
                    timeout=15_000,
                )
            except PWTimeoutError:
                raise AutoLoginError("Kakao 로그인 폼이 시간 내 나타나지 않음")

            # 4) 이메일 / 비밀번호 입력 — human-like keystroke delay
            email_inp = page.locator(
                'input[name="loginId"], input#loginId--1, input[name="email"]'
            ).first
            _human_type(page, email_inp, email)

            pw_inp = page.locator(
                'input[name="password"], input[type="password"]'
            ).first
            _human_type(page, pw_inp, password)

            # 5) 로그인 제출
            if not _try_click(
                page,
                [
                    'button.btn_g.highlight.submit',
                    'button[type="submit"]:has-text("로그인")',
                    'button[type="submit"]',
                ],
                timeout=5_000,
            ):
                raise AutoLoginError("Kakao 로그인 제출 버튼을 찾지 못함")

            # 6) Tistory 도메인으로 리다이렉트 대기 (hostname 검사 — substring 매칭 금지)
            deadline = time.monotonic() + LOGIN_DEADLINE_S
            while time.monotonic() < deadline:
                page.wait_for_timeout(500)
                parsed = urlparse(page.url)
                host = (parsed.hostname or "").lower()
                path = (parsed.path or "").lower()

                if host == "tistory.com" or host.endswith(".tistory.com"):
                    logger.info("Auto-login: redirect OK (url=%s)", page.url)
                    break

                # select_account 화면 자동 통과
                if host == "accounts.kakao.com" and "select_account" in path:
                    _try_click(
                        page,
                        [
                            'button:has-text("이 계정으로 시작하기")',
                            'a:has-text("이 계정으로 시작하기")',
                            'button.btn_agree',
                            'button.submit',
                        ],
                        timeout=3_000,
                    )
                    continue

                # OAuth 동의 화면 자동 통과
                if host == "kauth.kakao.com":
                    _try_click(
                        page,
                        [
                            'button:has-text("동의하고 계속하기")',
                            'button:has-text("전체 동의")',
                            'button.btn_agree',
                        ],
                        timeout=3_000,
                    )
                    continue

                # 로그인 폼에 머물러 있고 에러 배너 보이면 즉시 실패 (잘못된 비번 등)
                if host == "accounts.kakao.com" and (
                    "/login" in path or path in ("", "/")
                ):
                    try:
                        err_count = page.locator(
                            '.error_message, .desc_error, .txt_error, .ico_error'
                        ).count()
                    except Exception:
                        err_count = 0
                    if err_count:
                        raise AutoLoginError(
                            "Kakao 가 자격증명 거부 (에러 배너 노출) — "
                            "비밀번호 / CAPTCHA / 2FA 점검 필요"
                        )
            else:
                # while 가 break 없이 deadline 으로 끝남
                raise AutoLoginError(
                    f"{int(LOGIN_DEADLINE_S)}초 내 tistory.com 으로 리다이렉트되지 않음 "
                    f"— current_url={page.url}"
                )

            # 7) storage_state 저장 (기존 파일 덮어쓰기)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(state_file))
            size = state_file.stat().st_size
            if size == 0:
                raise AutoLoginError(f"저장된 storage_state 가 0 바이트: {state_file}")
            logger.info(
                "Auto-login: storage_state saved → %s (%d bytes)",
                state_file, size,
            )
            return state_file

        except AutoLoginError:
            raise
        except Exception as e:
            raise AutoLoginError(f"Auto-login unexpected error: {e}") from e
        finally:
            try:
                ctx.close()
            finally:
                browser.close()


# ---------------------------------------------------------------------
# CLI entrypoint  — `python -m src.auto_login`
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cli_state_path = os.environ.get("TISTORY_STATE_PATH", DEFAULT_STATE_PATH)
    cli_headless = os.environ.get("AUTO_LOGIN_HEADLESS", "true").lower() != "false"

    try:
        saved = renew_tistory_session(state_path=cli_state_path, headless=cli_headless)
        logger.info("renew_tistory_session OK → %s", saved)
        sys.exit(0)
    except AutoLoginError as e:
        logger.error("renew_tistory_session FAILED: %s", e)
        sys.exit(1)

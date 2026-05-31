"""Google Blogger v3 API 발행 모듈.

Tistory publisher 와 완전히 분리된 별도 트랙. Playwright 사용 없음.
OAuth2 user credentials (refresh token) 으로 인증하여 REST API 호출.

필요한 환경변수 (GitHub Secrets):
    GOOGLE_CLIENT_ID       — OAuth client id (Google Cloud Console)
    GOOGLE_CLIENT_SECRET   — OAuth client secret
    GOOGLE_REFRESH_TOKEN   — 로컬에서 1회 OAuth flow 로 발급한 refresh token

이미지 처리:
    Tistory 는 외부 URL 자동 가져오기 데드락 때문에 base64 인라인이 필요했지만,
    Blogger 는 그런 backend lock 이 없어서 외부 URL (Pollinations 등) 을 그대로
    HTML 에 박아도 정상 렌더링됨. base64 변환 불필요.
"""
from __future__ import annotations

import logging
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class BloggerPublishError(RuntimeError):
    """Raised when publishing to Blogger fails."""


SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _build_service():
    """Refresh-token 기반 credentials 로 Blogger v3 서비스 객체 생성."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    missing = [
        k for k, v in {
            "GOOGLE_CLIENT_ID": client_id,
            "GOOGLE_CLIENT_SECRET": client_secret,
            "GOOGLE_REFRESH_TOKEN": refresh_token,
        }.items() if not v
    ]
    if missing:
        raise BloggerPublishError(
            f"필수 환경변수 누락: {', '.join(missing)} — "
            "GitHub Secrets 에 설정해야 합니다."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    # cache_discovery=False — GitHub Actions runner 같은 임시 환경에서 디스크 쓰기 회피
    return build("blogger", "v3", credentials=creds, cache_discovery=False)


def publish_to_blogger(
    blog_id: str,
    title: str,
    html_content: str,
    tags: list[str] | None = None,
    is_draft: bool = False,
) -> str:
    """Blogger v3 API 로 글 1편 발행. 발행된 글의 URL 반환.

    Args:
        blog_id: Blogger 내부 blog id (숫자 문자열, e.g., "1234567890")
        title: 글 제목 (plain text)
        html_content: 본문 HTML
        tags: labels 로 사용될 태그 리스트
        is_draft: True 면 draft 로 저장 (기본 False = 즉시 공개)

    Returns:
        발행된 글의 공개 URL.

    Raises:
        BloggerPublishError: 인증/API/네트워크 오류 전반.
    """
    if not blog_id or blog_id.startswith("["):
        raise BloggerPublishError(
            f"blog_id 가 설정되지 않았거나 placeholder 상태: {blog_id!r}"
        )
    if not title or not html_content:
        raise BloggerPublishError("Empty title or content cannot be published")

    service = _build_service()

    body: dict = {
        "kind": "blogger#post",
        "title": title,
        "content": html_content,
    }
    if tags:
        body["labels"] = list(tags)

    try:
        result = (
            service.posts()
            .insert(blogId=blog_id, body=body, isDraft=is_draft)
            .execute()
        )
    except HttpError as e:
        status = getattr(e.resp, "status", "?")
        raise BloggerPublishError(
            f"Blogger API HTTP {status}: {e}"
        ) from e
    except Exception as e:
        raise BloggerPublishError(
            f"Unexpected error publishing to Blogger: {e}"
        ) from e

    post_url = result.get("url") or ""
    post_id = result.get("id") or ""
    logger.info(
        "Published to Blogger — blog_id=%s post_id=%s url=%s",
        blog_id, post_id, post_url,
    )
    return post_url

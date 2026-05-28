# generate_auth.py
from playwright.sync_api import sync_playwright

def save_login_state():
    with sync_playwright() as p:
        # headless=False로 설정하여 브라우저 화면이 보이게 합니다.
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # 티스토리 로그인 페이지로 이동
        page.goto("https://www.tistory.com/auth/login")
        
        print("\n" + "="*50)
        print("🚀 팝업된 브라우저에서 '카카오계정으로 로그인'을 클릭하고 로그인을 진행하세요.")
        print("   (캡차나 2단계 인증이 뜨면 모두 수동으로 완료해주세요)")
        print("✅ 로그인이 완전히 끝나고 티스토리 메인 화면이 나오면,")
        print("   이 터미널 창으로 돌아와서 [Enter] 키를 누르세요.")
        print("="*50 + "\n")
        
        input("로그인이 다 끝났다면 Enter 키를 누르세요: ")
        
        # 로그인 세션(쿠키) 정보를 state.json 파일로 저장
        context.storage_state(path="state.json")
        print("🎉 성공! 현재 폴더에 state.json 파일이 생성되었습니다.")
        
        browser.close()

if __name__ == "__main__":
    save_login_state()
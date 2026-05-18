# 공개 URL로 배포하기 (전체 앱)

**Vercel**은 서버리스라 Streamlit(WebSocket + 상시 프로세스) **전체 코드**를 호스팅할 수 없습니다.  
**Streamlit Community Cloud** 또는 **Docker 호스팅(Render 등)** 으로 공개 URL을 만듭니다.

제3자(저 포함)가 **당신 계정 없이** Streamlit Cloud에 앱을 등록하는 것은 **불가능**합니다(GitHub 권한·로그인 필요).  
아래 순서대로 **한 번만** 연결하면 누구나 URL로 접속할 수 있습니다.

---

## 방법 A: Streamlit Community Cloud (추천)

1. https://share.streamlit.io/ 에 GitHub로 로그인  
2. **New app** → Repository: `Mino94/hackerton-poscodx`, Branch: `main`  
3. Main file: **`app.py`**  
4. **Advanced** → Python 3.12 권장  
5. **Secrets** (`TOML`):

   ```toml
   OPENAI_API_KEY = "sk-..."  # 없으면 생략 가능(Fallback 데모)
   OPENAI_MODEL = "gpt-4o-mini"
   ```

6. **Deploy** — 발급 URL을 `https://xxxx.streamlit.app` 형태로 다른 사람에게 공유

**주의:** `requirements.txt`에 crewai 등 무거운 패키지가 있어 **첫 빌드가 수 분** 걸릴 수 있습니다. 실패 시 Cloud 로그에서 pip 오류를 확인하세요.

---

## 방법 B: Render (Docker — 이 저장소 포함)

1. https://render.com 에 가입 후 **New + Blueprint**  
2. `hackerton-poscodx` 저장소 연결 → 루트의 **`render.yaml`** 인식  
3. 환경 변수 `OPENAI_API_KEY` 입력(선택)  
4. 배포 완료 후 **공개 URL**(`onrender.com`) 공유  

무료 플랜은 미사용 시 슬립됩니다(첫 접속 시 기동 지연).

---

## 로컬에서 Docker 이미지 테스트

```bash
docker build -t autopm .
docker run --rm -p 8501:8501 -e OPENAI_API_KEY=optional autopm
```

브라우저: http://localhost:8501

---

## Vercel

`vercel-site/` 만 정적 랜딩으로 배포 가능합니다. **전체 Streamlit 앱**은 위 A/B를 사용하세요.

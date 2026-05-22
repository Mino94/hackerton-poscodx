# Streamlit Cloud — 데모만 (API 키 없이)

저장소 코드는 이미 준비됨. **가입하셨다면 아래만 하면 됩니다.**

## 1. 앱 만들기

1. https://share.streamlit.io/ 로그인  
2. **Create app**  
3. **Repository**: `Mino94/hackerton-poscodx`  
4. **Branch**: `main`  
5. **Main file**: `app.py`  
6. **App URL** (선택): 영문·숫자만, 예: `autopm-demo`

## 2. Secrets (비워도 됨)

데모만이면 **Secrets에 아무것도 넣지 않고** Deploy 해도 됩니다.  
(Cloud 런타임이 `python-pptx`·`/tmp/chroma` 등 기본값을 자동 설정합니다.)

권장: 저장소의 **`.streamlit/secrets.cloud.example.toml`** 내용을 Secrets에 붙여넣기.

- `OPENAI_API_KEY` 없음 → Fallback Markdown / Mock 초안 / Fallback PPT
- OpenAI 사용 시 Secrets에 `OPENAI_API_KEY` 추가

(`app.py`가 Secrets를 환경 변수로 옮깁니다.)

## 빠른 링크

- 배포 콘솔: https://share.streamlit.io/
- GitHub 앱 파일: https://github.com/Mino94/hackerton-poscodx/blob/main/app.py  
  → Create app → **Paste GitHub URL**에 위 주소 입력
- 로컬: `powershell -File scripts/open_streamlit_deploy.ps1`

## 3. 고급 설정 (권장)

- **Python version**: **3.12**  
- 첫 빌드: `requirements.txt`(deepagents·langchain 등) 때문에 **몇 분** 걸릴 수 있음.
- `main` 브랜치에 push 하면 연결된 앱은 보통 **자동 재배포**됩니다.

## 4. 문제 시

- **Deploy logs**에서 `pip install` 오류 확인  
- 무료 플랜 **리소스 한도**로 설치 실패하면 로그에 표시됨

배포가 끝나면 `https://<선택한이름>.streamlit.app` 주소로 다른 사람도 접속 가능합니다.

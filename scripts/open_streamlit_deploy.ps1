# Streamlit Community Cloud 배포 페이지 열기 (GitHub 연동은 브라우저에서 1회 필요)
$repo = "Mino94/hackerton-poscodx"
$branch = "main"
$appFile = "app.py"
$ghUrl = "https://github.com/$repo/blob/$branch/$appFile"

Write-Host "Streamlit Cloud 배포 안내"
Write-Host "1) 브라우저에서 로그인: https://share.streamlit.io/"
Write-Host "2) Create app → Paste GitHub URL:"
Write-Host "   $ghUrl"
Write-Host "3) Python 3.12, Secrets: .streamlit/secrets.cloud.example.toml 참고"
Write-Host "4) App URL 예: autopm-demo"

Start-Process "https://share.streamlit.io/"

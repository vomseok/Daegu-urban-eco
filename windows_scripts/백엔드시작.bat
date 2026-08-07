@echo off
REM ========================================
REM 그늘로 백엔드 서버 시작
REM ========================================
REM 아래 경로를 자신의 프로젝트 폴더로 변경하세요
REM 예: C:\Users\당신이름\Desktop\Daegu-urban-eco

cd /d %USERPROFILE%\Desktop\Daegu-urban-eco

REM 가상환경 활성화
call .venv\Scripts\activate.bat

REM 백엔드 서버 시작
echo.
echo ========================================
echo 그늘로 백엔드 서버 시작 중...
echo ========================================
echo.
python src/app.py

REM 오류 발생 시 일시중지
if errorlevel 1 (
    echo.
    echo 오류가 발생했습니다!
    echo 경로를 확인하세요: %USERPROFILE%\Desktop\Daegu-urban-eco
    pause
)

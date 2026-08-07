@echo off
REM ========================================
REM 그늘로 Flutter 모바일 앱 시작
REM ========================================
REM 아래 경로를 자신의 프로젝트 폴더로 변경하세요
REM 예: C:\Users\당신이름\Desktop\Daegu-urban-eco

cd /d %USERPROFILE%\Desktop\Daegu-urban-eco\flutter_app

echo.
echo ========================================
echo 그늘로 모바일 앱 시작 중...
echo ========================================
echo.
echo (잠깐만 기다려주세요...)
echo.

REM Flutter 앱 실행
flutter run

REM 오류 발생 시 일시중지
if errorlevel 1 (
    echo.
    echo 오류가 발생했습니다!
    echo.
    echo 확인할 사항:
    echo 1. Flutter가 설치되어 있나요?
    echo 2. 백엔드 서버(백엔드시작.bat)를 실행했나요?
    echo 3. 경로가 맞나요? %USERPROFILE%\Desktop\Daegu-urban-eco\flutter_app
    echo.
    pause
)

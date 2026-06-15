# PowerShell script to run the Nutag app using the local virtual environment

$VENV_PATH = ".venv\Scripts\streamlit.exe"

if (Test-Path $VENV_PATH) {
    Write-Host "Запуск приложения Nutag..." -ForegroundColor Green
    & $VENV_PATH run app.py
} else {
    Write-Host "Ошибка: Виртуальное окружение не найдено в .venv. Убедитесь, что вы находитесь в корне проекта." -ForegroundColor Red
    Pause
}

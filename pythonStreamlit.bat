@echo off
if not exist "env" (
    echo Creando entorno virtual...
    python -m venv env
)
call env\Scripts\activate
pip install streamlit pandas
streamlit run iptv_app.py
pause
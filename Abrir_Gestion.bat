@echo off
title Iniciando Sistema IPTV
echo Verificando librerias...
pip install streamlit pandas
echo Lanzando aplicacion...
streamlit run iptv_app.py
pause
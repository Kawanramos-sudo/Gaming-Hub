@echo off
chcp 65001 >nul
color 0a
cd /d "C:\Users\Elias\Desktop\Gaminghub v2.0\Gaminghub v2.0\Github"
python db_json.py
git add .
git commit -m "Atualizacao automatica"
git push origin main
pause

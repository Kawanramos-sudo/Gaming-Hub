@echo off
color 0a
cd /d "C:\Users\Kawan\Desktop\Gaminghub v2.0\Github"
python db_json.py
git add .
git commit -m "Atualização automática"
git push origin main
pause

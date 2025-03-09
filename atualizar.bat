@echo off
chcp 65001 >nul
color 0a
cd /d "C:\Users\Kawan\Desktop\Gaminghub v2.0\Github"
python db_json.py
git status
git pull origin main --rebase
>>>>>>> 53eb44e (Atualizacao automatica)
git add .
git commit -m "Atualizacao automatica"
git push origin main
pause

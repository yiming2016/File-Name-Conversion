@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] 安装依赖...
python -m pip install -r requirements.txt

echo [2/4] 打包 exe（使用 logo.ico 图标，输出到 成品-打开即用）...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "文件名翻译器" --icon logo.ico --distpath "..\成品-打开即用" --workpath build --specpath . main.py

echo [3/4] 同步词库数据到成品...
if exist "词库" xcopy /E /I /Y "词库\*" "..\成品-打开即用\词库\" >nul
if exist "使用说明.md" copy /Y "使用说明.md" "..\成品-打开即用\使用说明.md" >nul
if exist "app\logo.png" copy /Y "app\logo.png" "..\成品-打开即用\logo.png" >nul
if exist "app\github.png" copy /Y "app\github.png" "..\成品-打开即用\github.png" >nul
if exist "logo.ico" copy /Y "logo.ico" "..\成品-打开即用\logo.ico" >nul

echo [4/4] 完成！exe 位于: ..\成品-打开即用\文件名翻译器.exe
pause

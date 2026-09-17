@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] 安装依赖...
python -m pip install -r requirements.txt

echo [2/4] 打包 exe（使用 logo.ico 图标，输出到 软件）...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "文件名翻译器" --icon logo.ico --distpath "..\软件" --workpath build --specpath . main.py

echo [3/4] 同步词库与图标到 软件 文件夹...
if exist "词库" xcopy /E /I /Y "词库\*" "..\软件\词库\" >nul
if exist "使用说明.md" copy /Y "使用说明.md" "..\软件\使用说明.md" >nul
if exist "app\logo.png" copy /Y "app\logo.png" "..\软件\logo.png" >nul
if exist "app\github.png" copy /Y "app\github.png" "..\软件\github.png" >nul
if exist "logo.ico" copy /Y "logo.ico" "..\软件\logo.ico" >nul

echo [4/4] 完成！exe 位于: ..\软件\文件名翻译器.exe
pause

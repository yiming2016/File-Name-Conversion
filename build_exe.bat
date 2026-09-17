@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] 安装依赖...
python -m pip install -r requirements.txt

echo [2/4] 打包 exe（使用 logo.ico 图标，输出到 软件）...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "文件名翻译器" --icon logo.ico --add-data "logo.ico;." --add-data "app\logo.png;." --add-data "app\github.png;." --distpath "..\软件" --workpath build --specpath . main.py

echo [3/4] 同步词库与说明到 软件 文件夹...
if exist "词库" xcopy /E /I /Y "词库\*" "..\软件\词库\" >nul
if exist "使用说明.md" copy /Y "使用说明.md" "..\软件\使用说明.md" >nul

echo [4/4] 完成！exe 位于: ..\软件\文件名翻译器.exe
pause

@echo off
taskkill /F /IM python.exe >nul 2>&1
timeout /t 4 /nobreak >nul
cd /d C:\AI\ComfyUI_windows_portable
.\python_embeded\python.exe -m pip install --no-warn-script-location Pillow numpy "transformers>=4.45.0" accelerate huggingface_hub "psutil>=5.9" "imageio-ffmpeg>=0.5" > C:\AI\deps.log 2>&1
echo DONE > C:\AI\DEPS_DONE.txt

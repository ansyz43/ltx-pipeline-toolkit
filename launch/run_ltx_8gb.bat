@echo off
cd /d C:\AI\ComfyUI_windows_portable
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --fast fp16_accumulation fp8_matrix_mult --fast-disk --vram-headroom 1.0 --cache-ram 6 --preview-method latent2rgb
pause

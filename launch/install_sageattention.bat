@echo off
taskkill /F /IM python.exe >nul 2>&1
timeout /t 4 /nobreak >nul
cd /d C:\AI\ComfyUI_windows_portable
.\python_embeded\python.exe -m pip install --no-warn-script-location "https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post4/sageattention-2.2.0%2Bcu130torch2.9.0andhigher.post4-cp39-abi3-win_amd64.whl" > C:\AI\sage_up.log 2>&1
.\python_embeded\python.exe -c "import sageattention as s, inspect; print('SAGE', getattr(s,'__version__','?')); print('fp8:', [n for n in dir(s) if 'fp8' in n])" >> C:\AI\sage_up.log 2>&1
echo DONE > C:\AI\SAGE_DONE.txt

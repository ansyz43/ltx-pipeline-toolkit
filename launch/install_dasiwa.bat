@echo off
cd /d C:\AI\ComfyUI_windows_portable\ComfyUI\custom_nodes
git clone --depth 1 https://github.com/darksidewalker/ComfyUI-DaSiWa-Nodes.git > C:\AI\dasiwa_nodes.log 2>&1
if exist ComfyUI-DaSiWa-Nodes\requirements.txt (
  ..\..\python_embeded\python.exe -m pip install --no-warn-script-location -r ComfyUI-DaSiWa-Nodes\requirements.txt >> C:\AI\dasiwa_nodes.log 2>&1
)
echo DONE > C:\AI\DASIWA_NODES_DONE.txt

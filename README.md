# ScreenTranslatorAI
🖥️ Screen Translator AI (终极屏幕翻译工具)
![alt text](https://img.shields.io/badge/Python-3.10%2B-blue)

![alt text](https://img.shields.io/badge/GUI-PyQt6-green)

![alt text](https://img.shields.io/badge/AI-Ollama-orange)

![alt text](https://img.shields.io/badge/License-MIT-purple)
Screen Translator AI 是一款基于 PyQt6 构建的现代化屏幕截图翻译与视觉分析工具。它深度集成了 Ollama 本地大模型 与 在线 API (OpenAI 兼容)，支持“截图即译”、“深度追问”、“语音朗读”等功能。
本项目专为追求 隐私安全、极速响应 和 深度交互 的用户设计。
![alt text](https://via.placeholder.com/800x400?text=Application+Screenshot+Placeholder)

(建议在此处替换为实际软件运行截图)
✨ 核心特性 (Key Features)
⚡ 双引擎混合动力 (Hybrid AI Engine)
在线优先：支持配置 OpenAI/DeepSeek 等在线 API，获取最强模型体验。
本地兜底：网络不可用时，自动无缝降级至本地 Ollama (Qwen-VL/Llama-Vision) 模型。
📷 无痕系统级截图
调用系统原生截图工具 (Windows Snipping Tool)，体验丝滑。
阅后即焚：自动监控并清理系统生成的截图文件，仅在内存中处理数据，不占用硬盘空间。
💬 深度追问模式 (Chat Mode)
防闪烁气泡 UI：复刻 ChatGPT 体验，支持流式输出。
动态思考：翻译时使用“极速模式”，追问时自动切换“深度思考”模式（CoT），支持上下文多轮对话。
多模态交互：支持在对话框中上传本地图片发送给 AI。
🔊 完美语音朗读 (Robust TTS)
内置单例 TTS 队列服务，彻底解决 pyttsx3 在多线程下的卡死和无声问题。
🎨 现代化 UI 设计
三段式布局：图片预览 -> 译文区 -> 原文区。
自适应高度：窗口根据文本内容自动伸缩。
大图灯箱：支持滚轮缩放、拖拽查看图片细节。
💾 数据管理
历史回溯：内存级历史记录，点击即可完整重现当时的弹窗状态。
本地收藏：一键将图片和翻译结果持久化保存到本地文件夹。
🛠️ 安装指南 (Installation)
1. 环境准备
确保已安装 Python 3.10 或更高版本，以及 Ollama。
2. 克隆项目
code
Bash
git clone https://github.com/your-username/screen-translator-ai.git
cd screen-translator-ai
3. 安装依赖
code
Bash
pip install -r requirements.txt
(如果没有 requirements.txt，请使用以下命令安装)：
code
Bash
pip install PyQt6 ollama pyttsx3 keyboard pyperclip pillow requests
4. 准备 AI 模型
本项目默认使用 qwen3-vl:8b 作为本地视觉模型。请确保在终端运行过以下命令：
code
Bash
ollama pull qwen3-vl:8b
(你也可以在软件设置中更改为其他视觉模型，如 llama3.2-vision)
🚀 使用说明 (Usage)
启动程序：
code
Bash
python main.py
触发截图：
默认快捷键：Ctrl + Alt + F
屏幕变暗后，框选需要翻译的区域即可。
功能操作：
🔊：朗读原文或译文。
📋：复制内容。
⭐：收藏本次结果到 saved_translations 目录。
💬：进入对话模式，针对图片细节向 AI 提问。
托盘菜单：
右击任务栏右下角的“文”字图标，可进行设置 API、修改快捷键或查看历史。
⚙️ 配置与设置 (Configuration)
在托盘菜单点击 “⚙️ API 设置” 即可打开配置面板：
启用在线 AI：勾选后优先使用在线接口。
API Key：填入你的密钥 (如 sk-xxxx)。
Base URL：支持 OpenAI 官方或第三方中转地址 (如 https://api.deepseek.com)。
Online Model：在线模型名称 (如 gpt-4o, deepseek-chat)。
Local Model：本地 Ollama 模型名称 (如 qwen3-vl:8b)。
📦 打包为 EXE (Build)
如果你想将程序打包为独立的 Windows 可执行文件：
安装 PyInstaller：
code
Bash
pip install pyinstaller
准备一个图标文件 icon.ico (可选)。
执行打包命令：
code
Bash
pyinstaller -F -w -i icon.ico -n "ScreenTranslatorAI" main.py
在 dist 文件夹中找到生成的 .exe 文件。
注意：打包后的 EXE 仅包含程序逻辑，不包含 AI 模型。运行 EXE 的电脑仍需安装并启动 Ollama。
🤝 贡献 (Contributing)
欢迎提交 Issue 或 Pull Request！
Fork 本仓库
新建分支 (git checkout -b feature/AmazingFeature)
提交更改 (git commit -m 'Add some AmazingFeature')
推送到分支 (git push origin feature/AmazingFeature)
提交 Pull Request
📄 许可证 (License)
本项目基于 MIT 许可证开源 - 详见 LICENSE 文件。

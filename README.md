# YourTalesAI (myAI)

Local Streamlit chat app backed by [Ollama](https://ollama.com), with optional local Stable Diffusion image generation/editing via Hugging Face diffusers.

No cloud API keys are required for chat. Image models download from Hugging Face on first use.

## What you need

**Chat**

- Python 3.10+
- Ollama running
- At least one supported chat model pulled

**Image gen / edit**

- Everything for chat, plus:
- PyTorch + Diffusers stack
- About 6-8GB GPU VRAM recommended (CPU works but is slow)
- Network for first-time model downloads

### Supported chat models (sidebar picker)

Pull one or more of these with Ollama:

- dolphin-llama3
- dolphin-mistral
- wizard-vicuna-uncensored

Example:

`powershell
ollama pull dolphin-llama3
ollama pull dolphin-mistral
ollama pull wizard-vicuna-uncensored
`

### Image models

Selected in the sidebar (Stable Diffusion 1.5 family and variants). The first request for a given model downloads the checkpoint from Hugging Face (often multi-GB). Generated images are written under generated/ (gitignored).

## Setup

### 1. Install Ollama

Windows (PowerShell):

`powershell
irm https://ollama.com/install.ps1 | iex
`

Start the Ollama service (if it is not already running):

`powershell
ollama serve
`

Then pull at least one supported chat model (see above).

### 2. Clone and create a virtualenv

`powershell
cd myAI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
`

### 3. Install Python packages

Install from the requirements file:

`powershell
pip install -r requirements.txt
`

That covers chat (streamlit, ollama, Pillow).

For image generation, also install Diffusers helpers and PyTorch:

`powershell
pip install -r requirements-image.txt
`

Install PyTorch for your platform from https://pytorch.org. NVIDIA CUDA 12.4 example used in development:

`powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
`

Without the image stack, the app UI can still load for chat; image generate/edit will fail until those packages (and preferably a CUDA GPU) are available.

### 4. Run the app

Terminal 1 - Ollama:

`powershell
ollama serve
`

Terminal 2 - Streamlit:

`powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
`

Open the URL Streamlit prints (usually http://localhost:8501).

## Project layout

- pp.py - Streamlit UI, chat, image prompts, sidebar
- image_gen.py - Local SD pipelines
- ssets/ - Logos and avatars
- settings.json - Saved chat/image model preferences
- chat_history.json - Local chat store (starts empty)
- generated/ - Output images (created at runtime; not in git)
- 
equirements.txt - Chat / core Python deps
- 
equirements-image.txt - Extra deps for local image generation (install PyTorch separately)

## Troubleshooting

- **Chat errors / empty model list:** Ensure ollama serve is running and you have pulled at least one supported model (ollama list).
- **Wrong model name in settings.json:** The app tries to match tags like :latest; if needed, pick a model again in the sidebar.
- **Image import / CUDA errors:** Install the Diffusers + PyTorch stack for your GPU; CPU-only Torch will run but may be very slow.
- **First image is slow / large download:** Expected - the selected Hugging Face checkpoint downloads once and is cached locally.
- **Stale UI after pulling code:** Hard-refresh the browser; restart streamlit run app.py.
- **README looks full of spaces/NULs:** File must be UTF-8. Re-save as UTF-8 if an editor rewrote it as UTF-16.

## Notes for contributors

- .venv/ and generated/ are gitignored - do not commit them.
- settings.json and chat_history.json are local state; safe to keep empty/default when sharing.
- myAI.iml is an IntelliJ/PyCharm module file and is not required to run the app.

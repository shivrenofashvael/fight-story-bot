# SDXL Anime ControlNet — Animagine XL 3.1 + xinsir Canny ControlNet
FROM runpod/worker-comfyui:5.8.5-base

# ── Download Animagine XL 3.1 anime checkpoint ──
RUN wget -q -O /comfyui/models/checkpoints/animagine-xl-3.1.safetensors \
    "https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors"

# ── Download xinsir ControlNet Canny SDXL ──
RUN mkdir -p /comfyui/models/controlnet && \
    wget -q -O /comfyui/models/controlnet/controlnet-canny-sdxl.safetensors \
    "https://huggingface.co/xinsir/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors"

# ── Install ControlNet aux preprocessors (Canny, Depth, etc.) ──
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git && \
    cd comfyui_controlnet_aux && \
    pip install -r requirements.txt

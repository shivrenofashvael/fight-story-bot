# SDXL Anime + Multi-ControlNet (Canny + OpenPose + Depth)
# Maximum pose preservation for fight scene restyling
FROM runpod/worker-comfyui:5.8.5-base

# ── Animagine XL 3.1 anime checkpoint (~6.5GB) ──
RUN wget -q -O /comfyui/models/checkpoints/animagine-xl-3.1.safetensors \
    "https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors"

# ── xinsir ControlNet models for SDXL (best-in-class) ──
RUN mkdir -p /comfyui/models/controlnet && \
    wget -q -O /comfyui/models/controlnet/controlnet-canny-sdxl.safetensors \
    "https://huggingface.co/xinsir/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" && \
    wget -q -O /comfyui/models/controlnet/controlnet-openpose-sdxl.safetensors \
    "https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors" && \
    wget -q -O /comfyui/models/controlnet/controlnet-depth-sdxl.safetensors \
    "https://huggingface.co/xinsir/controlnet-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors"

# ── ControlNet aux preprocessors (Canny, OpenPose, Depth, etc.) ──
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git && \
    cd comfyui_controlnet_aux && \
    pip install -r requirements.txt

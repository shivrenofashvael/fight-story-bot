FROM runpod/worker-comfyui:5.8.5-base

# ── Install XLabs Flux ControlNet custom nodes ──
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/XLabs-AI/x-flux-comfyui.git && \
    cd x-flux-comfyui && \
    python setup.py

# ── Install ControlNet aux preprocessors (Canny, Depth, Lineart) ──
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git && \
    cd comfyui_controlnet_aux && \
    pip install -r requirements.txt

# ── Download Flux dev fp8 checkpoint ──
RUN wget -q -O /comfyui/models/checkpoints/flux1-dev-fp8.safetensors \
    "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors"

# ── Download CLIP models for Flux ──
RUN wget -q -O /comfyui/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" && \
    wget -q -O /comfyui/models/text_encoders/clip_l.safetensors \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"

# ── Download Flux VAE (from ungated Comfy-Org mirror) ──
RUN wget -q -O /comfyui/models/vae/ae.safetensors \
    "https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/ae.safetensors"

# ── Download XLabs Flux ControlNet models ──
RUN mkdir -p /comfyui/models/xlabs/controlnets && \
    wget -q -O /comfyui/models/xlabs/controlnets/flux-canny-controlnet-v3.safetensors \
    "https://huggingface.co/XLabs-AI/flux-controlnet-collections/resolve/main/flux-canny-controlnet-v3.safetensors"

# Start from the image that ALREADY has Flux dev fp8 + CLIP + VAE
FROM runpod/worker-comfyui:5.8.5-flux1-dev-fp8

# ── Install XLabs Flux ControlNet custom nodes ──
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/XLabs-AI/x-flux-comfyui.git && \
    cd x-flux-comfyui && \
    pip install -e .

# ── Install ControlNet aux preprocessors (Canny, Depth, Lineart) ──
RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git && \
    cd comfyui_controlnet_aux && \
    pip install -r requirements.txt

# ── Download XLabs Flux ControlNet Canny model (~3.6GB) ──
RUN mkdir -p /comfyui/models/xlabs/controlnets && \
    wget -q -O /comfyui/models/xlabs/controlnets/flux-canny-controlnet-v3.safetensors \
    "https://huggingface.co/XLabs-AI/flux-controlnet-collections/resolve/main/flux-canny-controlnet-v3.safetensors"

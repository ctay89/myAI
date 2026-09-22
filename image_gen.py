"""Local Stable Diffusion image generation (GPU, ~6–8GB VRAM)."""

from __future__ import annotations

import streamlit as st

DEFAULT_IMAGE_MODEL = "realistic_vision"
DEFAULT_STRENGTH = 0.65
DEFAULT_SD15_NEGATIVE = (
    "blurry, low quality, deformed, extra fingers, watermark, text"
)
DEFAULT_ANIME_NEGATIVE = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, "
    "extra digit, fewer digits, cropped, worst quality, low quality, "
    "jpeg artifacts, signature, watermark, username, blurry, deformed"
)

# Recommended MSE VAE for Realistic Vision (noVAE checkpoint)
SD15_VAE_MSE = "stabilityai/sd-vae-ft-mse"


def _sd15(
    label: str,
    repo: str,
    *,
    style: str = "Default",
    negative_prompt: str = DEFAULT_SD15_NEGATIVE,
    vae: str | None = None,
    steps: int = 30,
    guidance: float = 7.5,
) -> dict:
    cfg: dict = {
        "label": label,
        "style": style,
        "kind": "sd15",
        "repo": repo,
        "steps": steps,
        "guidance": guidance,
        "size": 512,
        "strength": 0.65,
        "negative_prompt": negative_prompt,
    }
    if vae:
        cfg["vae"] = vae
    return cfg


# Picker options: key -> config
IMAGE_MODELS: dict[str, dict] = {
    "realistic_vision": _sd15(
        "Realistic Vision (Photo Realism)",
        "SG161222/Realistic_Vision_V5.1_noVAE",
        style="Photo Realism",
        vae=SD15_VAE_MSE,
    ),
    "dreamshaper8": _sd15(
        "Dreamshaper 8 (Illustrations)",
        "Lykon/dreamshaper-8",
        style="Illustrations",
    ),
    "anything_v5": _sd15(
        "Anything V5 (Manga & Anime)",
        "genai-archive/anything-v5",
        style="Manga & Anime",
        negative_prompt=DEFAULT_ANIME_NEGATIVE,
    ),
}


def image_model_keys() -> list[str]:
    return list(IMAGE_MODELS.keys())


def image_model_label(key: str) -> str:
    cfg = IMAGE_MODELS.get(key) or IMAGE_MODELS[DEFAULT_IMAGE_MODEL]
    return str(cfg["label"])


def image_model_style(key: str) -> str:
    """Short style tag shown under the image-model picker."""
    cfg = IMAGE_MODELS.get(key) or IMAGE_MODELS[DEFAULT_IMAGE_MODEL]
    return str(cfg.get("style") or "Default")


def image_model_short_label(key: str) -> str:
    """Model name without the parenthetical style suffix."""
    return image_model_label(key).split(" (", 1)[0]


def resolve_image_model(key: str | None) -> str:
    if key in IMAGE_MODELS:
        return str(key)
    return DEFAULT_IMAGE_MODEL


def _negative_for(key: str, negative_prompt: str = "") -> str | None:
    """Use an explicit negative when given; otherwise the model default."""
    text = (negative_prompt or "").strip()
    if not text:
        text = str(IMAGE_MODELS.get(key, {}).get("negative_prompt") or "").strip()
    return text or None


def clear_image_pipelines() -> None:
    """Drop cached pipelines so switching models frees VRAM."""
    import torch

    try:
        get_txt2img_pipeline.clear()
    except Exception:
        pass
    try:
        get_img2img_pipeline.clear()
    except Exception:
        pass
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _device_dtype():
    import torch

    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32


def _configure_pipe(pipe):
    device, _ = _device_dtype()
    if device == "cuda":
        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()
        if hasattr(pipe, "enable_vae_tiling"):
            pipe.enable_vae_tiling()
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe = pipe.to("cuda")
    else:
        pipe = pipe.to("cpu")
    pipe.set_progress_bar_config(disable=True)
    return pipe


def _load_sd15(key: str, dtype):
    from diffusers import AutoencoderKL, StableDiffusionPipeline

    cfg = IMAGE_MODELS[key]
    kwargs: dict = {
        "torch_dtype": dtype,
        "safety_checker": None,
        "requires_safety_checker": False,
    }
    vae_repo = cfg.get("vae")
    if vae_repo:
        kwargs["vae"] = AutoencoderKL.from_pretrained(str(vae_repo), torch_dtype=dtype)
    return StableDiffusionPipeline.from_pretrained(str(cfg["repo"]), **kwargs)


@st.cache_resource(show_spinner="Loading image model…")
def get_txt2img_pipeline(model_key: str):
    key = resolve_image_model(model_key)
    kind = IMAGE_MODELS[key]["kind"]
    _, dtype = _device_dtype()

    if kind == "sd15":
        pipe = _load_sd15(key, dtype)
    else:
        raise ValueError(f"Unknown image model: {key}")

    return _configure_pipe(pipe)


@st.cache_resource(show_spinner="Loading image-edit pipeline…")
def get_img2img_pipeline(model_key: str):
    from diffusers import AutoPipelineForImage2Image

    return AutoPipelineForImage2Image.from_pipe(get_txt2img_pipeline(model_key))


def _generator(seed: int | None):
    import torch

    if seed is None:
        return None
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return torch.Generator(device=device).manual_seed(int(seed))


def generate_image(
    prompt: str,
    *,
    model_key: str = DEFAULT_IMAGE_MODEL,
    negative_prompt: str = "",
    steps: int | None = None,
    guidance_scale: float | None = None,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
):
    """Generate a PIL image from a text prompt using the selected model."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Prompt must not be empty.")

    key = resolve_image_model(model_key)
    cfg = IMAGE_MODELS[key]
    steps = int(cfg["steps"] if steps is None else steps)
    guidance_scale = float(cfg["guidance"] if guidance_scale is None else guidance_scale)
    size = int(cfg["size"] if width is None else width)
    height = int(cfg["size"] if height is None else height)
    neg = _negative_for(key, negative_prompt)

    pipe = get_txt2img_pipeline(key)
    result = pipe(
        prompt=prompt,
        negative_prompt=neg,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        width=size,
        height=height,
        generator=_generator(seed),
    )
    return result.images[0]


def edit_image(
    prompt: str,
    init_image,
    *,
    model_key: str = DEFAULT_IMAGE_MODEL,
    negative_prompt: str = "",
    steps: int | None = None,
    guidance_scale: float | None = None,
    strength: float | None = None,
    seed: int | None = None,
):
    """Regenerate from a previous image + edit prompt (img2img)."""
    from PIL import Image

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Edit prompt must not be empty.")

    key = resolve_image_model(model_key)
    cfg = IMAGE_MODELS[key]
    steps = int(cfg["steps"] if steps is None else steps)
    guidance_scale = float(cfg["guidance"] if guidance_scale is None else guidance_scale)
    strength = float(cfg.get("strength", DEFAULT_STRENGTH) if strength is None else strength)
    size = int(cfg["size"])
    neg = _negative_for(key, negative_prompt)

    image = init_image.convert("RGB").resize(
        (size, size),
        Image.Resampling.LANCZOS,
    )
    pipe = get_img2img_pipeline(key)
    result = pipe(
        prompt=prompt,
        image=image,
        negative_prompt=neg,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        strength=strength,
        generator=_generator(seed),
    )
    return result.images[0]

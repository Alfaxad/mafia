from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import modal


APP_NAME = "mafia-gemma4-inference"
SECRET_NAME = "mafia-finetune-secrets"

HF_MODEL_REPO = "build-small-hackathon/mafia-gemma-4-12B-it"
BASE_MODEL_REPO = "google/gemma-4-12B-it"
GGUF_MODEL_REPO = "build-small-hackathon/mafia-gemma-4-12B-it-gguf"
GGUF_FILENAME = "gemma-4-12b-it.Q8_0.gguf"
LLAMA_CPP_COMMIT = "18ef86ecec723361362a332a79b4d913fd724d40"

MODEL_CACHE = Path("/model_cache")
GGUF_CACHE = Path("/gguf_cache")
LLAMA_CPP_ROOT = Path("/opt/llama.cpp")

app = modal.App(APP_NAME)
model_cache_volume = modal.Volume.from_name("mafia-gemma4-model-cache", create_if_missing=True)
gguf_cache_volume = modal.Volume.from_name("mafia-gemma4-gguf-cache", create_if_missing=True)


hf_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "git-lfs", "curl", "build-essential", "cmake", "pkg-config")
    .run_commands(
        "pip install --upgrade pip uv",
        "uv pip install --system "
        "'torch>=2.8.0' 'triton>=3.4.0' torchvision bitsandbytes accelerate "
        "sentencepiece protobuf safetensors huggingface_hub hf_transfer "
        "'datasets==4.3.0' timm torchcodec numpy",
        "uv pip install --system "
        "'unsloth[base] @ git+https://github.com/unslothai/unsloth' "
        "'unsloth_zoo[base] @ git+https://github.com/unslothai/unsloth-zoo'",
        "uv pip install --system --no-deps "
        "'transformers==5.11.0' 'tokenizers>=0.22.0,<=0.23.0'",
    )
    .env(
        {
            "HF_HOME": str(MODEL_CACHE),
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "HF_XET_HIGH_PERFORMANCE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "PYTHONUNBUFFERED": "1",
        }
    )
)

gguf_image = (
    modal.Image.from_registry("nvidia/cuda:12.6.3-devel-ubuntu22.04", add_python="3.11")
    .apt_install("git", "cmake", "build-essential", "curl", "libcurl4-openssl-dev", "ca-certificates")
    .run_commands(
        "pip install --upgrade pip uv",
        "uv pip install --system huggingface_hub hf_transfer requests",
        f"git clone https://github.com/ggml-org/llama.cpp.git {LLAMA_CPP_ROOT}",
        f"cd {LLAMA_CPP_ROOT} && git checkout {LLAMA_CPP_COMMIT}",
        "ln -sf /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1",
        (
            f"cd {LLAMA_CPP_ROOT} && "
            "cmake -B build "
            "-DGGML_CUDA=ON "
            "'-DCMAKE_CUDA_ARCHITECTURES=80;89' "
            "'-DCMAKE_EXE_LINKER_FLAGS=-L/usr/local/cuda/lib64/stubs -Wl,-rpath-link,/usr/local/cuda/lib64/stubs' "
            "-DLLAMA_CURL=ON "
            "-DLLAMA_BUILD_SERVER=ON "
            "-DLLAMA_BUILD_UI=OFF "
            "-DLLAMA_BUILD_TESTS=OFF "
            "-DLLAMA_BUILD_EXAMPLES=OFF "
            "-DCMAKE_BUILD_TYPE=Release"
        ),
        f"cmake --build {LLAMA_CPP_ROOT}/build --target llama-server -j $(nproc)",
    )
    .env(
        {
            "HF_HOME": str(MODEL_CACHE),
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "HF_XET_HIGH_PERFORMANCE": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
)


def _json_text_only(text: str) -> str:
    return (text or "").strip()


@app.cls(
    image=hf_image,
    gpu="A100-40GB",
    volumes={str(MODEL_CACHE): model_cache_volume},
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=10 * 60,
    startup_timeout=30 * 60,
    scaledown_window=20 * 60,
    max_containers=1,
)
class MergedBF16Model:
    @modal.enter()
    def load(self) -> None:
        import torch
        import unsloth  # noqa: F401
        from unsloth import FastModel
        from unsloth.chat_templates import get_chat_template

        token = os.environ["HF_API_KEY"]
        torch.set_float32_matmul_precision("high")
        self.model, self.tokenizer = FastModel.from_pretrained(
            model_name=HF_MODEL_REPO,
            dtype=torch.bfloat16,
            max_seq_length=4096,
            load_in_4bit=False,
            full_finetuning=False,
            token=token,
        )
        self.tokenizer = get_chat_template(self.tokenizer, chat_template="gemma-4")
        self.model.eval()
        self.loaded_at = time.time()
        self.dtype = "bfloat16"

    @modal.method()
    def generate(
        self,
        prompt: str,
        max_tokens: int = 192,
        temperature: float = 0.0,
        top_p: float | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        import torch

        started = time.perf_counter()
        temp = float(temperature or 0.0)
        conversation = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        inputs = self.tokenizer.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
        ).to("cuda")
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": int(max_tokens),
            "use_cache": True,
            "do_sample": bool(temp > 0),
        }
        if temp > 0:
            generation_kwargs["temperature"] = temp
            generation_kwargs["top_p"] = float(top_p if top_p is not None else 0.95)
            generation_kwargs["top_k"] = int(top_k if top_k is not None else 64)
        with torch.inference_mode():
            output = self.model.generate(**inputs, **generation_kwargs)
        input_tokens = int(inputs["input_ids"].shape[-1])
        decoded = self.tokenizer.decode(output[0][input_tokens:], skip_special_tokens=True)
        completion_tokens = int(output.shape[-1] - input_tokens)
        return {
            "text": _json_text_only(decoded),
            "backend": "modal_transformers_bf16",
            "model": HF_MODEL_REPO,
            "dtype": self.dtype,
            "prompt_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "sampler": {
                "temperature": temp,
                "top_p": generation_kwargs.get("top_p"),
                "top_k": generation_kwargs.get("top_k"),
            },
            "latency_seconds": round(time.perf_counter() - started, 4),
            "gpu": "A100-40GB",
        }


@app.cls(
    image=hf_image,
    gpu="A100-40GB",
    volumes={str(MODEL_CACHE): model_cache_volume},
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=10 * 60,
    startup_timeout=30 * 60,
    scaledown_window=20 * 60,
    max_containers=1,
)
class BaseBF16Model:
    @modal.enter()
    def load(self) -> None:
        import torch
        import unsloth  # noqa: F401
        from unsloth import FastModel
        from unsloth.chat_templates import get_chat_template

        token = os.environ["HF_API_KEY"]
        torch.set_float32_matmul_precision("high")
        self.model, self.tokenizer = FastModel.from_pretrained(
            model_name=BASE_MODEL_REPO,
            dtype=torch.bfloat16,
            max_seq_length=4096,
            load_in_4bit=False,
            full_finetuning=False,
            token=token,
        )
        self.tokenizer = get_chat_template(self.tokenizer, chat_template="gemma-4")
        self.model.eval()
        self.loaded_at = time.time()
        self.dtype = "bfloat16"

    @modal.method()
    def generate(
        self,
        prompt: str,
        max_tokens: int = 192,
        temperature: float = 0.0,
        top_p: float | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        import torch

        started = time.perf_counter()
        temp = float(temperature or 0.0)
        conversation = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        inputs = self.tokenizer.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
        ).to("cuda")
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": int(max_tokens),
            "use_cache": True,
            "do_sample": bool(temp > 0),
        }
        if temp > 0:
            generation_kwargs["temperature"] = temp
            generation_kwargs["top_p"] = float(top_p if top_p is not None else 0.95)
            generation_kwargs["top_k"] = int(top_k if top_k is not None else 64)
        with torch.inference_mode():
            output = self.model.generate(**inputs, **generation_kwargs)
        input_tokens = int(inputs["input_ids"].shape[-1])
        decoded = self.tokenizer.decode(output[0][input_tokens:], skip_special_tokens=True)
        completion_tokens = int(output.shape[-1] - input_tokens)
        return {
            "text": _json_text_only(decoded),
            "backend": "modal_transformers_base_bf16",
            "model": BASE_MODEL_REPO,
            "dtype": self.dtype,
            "prompt_tokens": input_tokens,
            "completion_tokens": completion_tokens,
            "sampler": {
                "temperature": temp,
                "top_p": generation_kwargs.get("top_p"),
                "top_k": generation_kwargs.get("top_k"),
            },
            "latency_seconds": round(time.perf_counter() - started, 4),
            "gpu": "A100-40GB",
        }


@app.cls(
    image=gguf_image,
    gpu="A100-40GB",
    volumes={str(MODEL_CACHE): model_cache_volume, str(GGUF_CACHE): gguf_cache_volume},
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=10 * 60,
    startup_timeout=30 * 60,
    scaledown_window=20 * 60,
    max_containers=1,
)
class GGUFQ8Model:
    @modal.enter()
    def load(self) -> None:
        import requests
        from huggingface_hub import hf_hub_download

        token = os.environ["HF_API_KEY"]
        GGUF_CACHE.mkdir(parents=True, exist_ok=True)
        self.model_path = GGUF_CACHE / GGUF_FILENAME
        if not self.model_path.exists() or self.model_path.stat().st_size < 12_000_000_000:
            downloaded = hf_hub_download(
                repo_id=GGUF_MODEL_REPO,
                filename=GGUF_FILENAME,
                repo_type="model",
                token=token,
                local_dir=str(GGUF_CACHE),
            )
            self.model_path = Path(downloaded)
            gguf_cache_volume.commit()

        self.port = 8080
        server = LLAMA_CPP_ROOT / "build" / "bin" / "llama-server"
        cmd = [
            str(server),
            "-m",
            str(self.model_path),
            "-c",
            "4096",
            "-ngl",
            "99",
            "-np",
            "1",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--no-webui",
            "--no-warmup",
            "--log-disable",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        health_url = f"http://127.0.0.1:{self.port}/health"
        last_error = ""
        for _ in range(180):
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited during startup with code {self.proc.returncode}")
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    self.loaded_at = time.time()
                    return
                last_error = f"status={response.status_code} body={response.text[:200]}"
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(2)
        raise RuntimeError(f"llama-server did not become healthy: {last_error}")

    @modal.method()
    def generate(
        self,
        prompt: str,
        max_tokens: int = 192,
        temperature: float = 0.0,
        top_p: float | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        import requests

        started = time.perf_counter()
        temp = float(temperature or 0.0)
        payload = {
            "model": "mafia-gemma-4-12b-it-q8-gguf",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
            "top_p": float(top_p if top_p is not None else 0.95),
            "top_k": int(top_k if top_k is not None else (64 if temp > 0 else 1)),
            "max_tokens": int(max_tokens),
        }
        response = requests.post(
            f"http://127.0.0.1:{self.port}/v1/chat/completions",
            json=payload,
            timeout=240,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        timings = data.get("timings") or {}
        return {
            "text": _json_text_only(text),
            "backend": "modal_gguf_q8",
            "model": f"{GGUF_MODEL_REPO}/{GGUF_FILENAME}",
            "dtype": "Q8_0",
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "prompt_tokens_per_second": timings.get("prompt_per_second"),
            "completion_tokens_per_second": timings.get("predicted_per_second"),
            "sampler": {
                "temperature": payload["temperature"],
                "top_p": payload["top_p"],
                "top_k": payload["top_k"],
            },
            "latency_seconds": round(time.perf_counter() - started, 4),
            "gpu": "A100-40GB",
        }

    @modal.exit()
    def cleanup(self) -> None:
        proc = getattr(self, "proc", None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


SMOKE_PROMPT = """You are Casey in a 7-player Mafia game.
Role: Mafia
Alive players: Ariel, Blake, Casey, Devon, Emery, Finley, Gray
Original role counts: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
Your Mafia teammate(s): Blake.

Public transcript:
Night 1: No one died during the night.
Day 1 Ariel: I want concrete vote reasons, not vague suspicion.

Architecture: WOLF + ReVAC core with GRAIL constraints.

Night 2. The Mafia must choose exactly one non-Mafia player to kill from:
['Ariel', 'Devon', 'Emery', 'Finley', 'Gray']

Return JSON exactly:
{"target": "one exact candidate name"}
"""


@app.local_entrypoint()
def smoke(target: str = "both", temperature: float = 1.0, top_p: float = 0.95, top_k: int = 64) -> None:
    targets = {"both", "transformers", "base", "gguf"}
    if target not in targets:
        raise ValueError(f"target must be one of {sorted(targets)}")
    if target in {"both", "transformers"}:
        model = MergedBF16Model()
        print(json.dumps({"target": "transformers", "result": model.generate.remote(SMOKE_PROMPT, 96, temperature, top_p, top_k)}, indent=2))
    if target in {"both", "base"}:
        model = BaseBF16Model()
        print(json.dumps({"target": "base", "result": model.generate.remote(SMOKE_PROMPT, 96, temperature, top_p, top_k)}, indent=2))
    if target in {"both", "gguf"}:
        model = GGUFQ8Model()
        print(json.dumps({"target": "gguf", "result": model.generate.remote(SMOKE_PROMPT, 96, temperature, top_p, top_k)}, indent=2))

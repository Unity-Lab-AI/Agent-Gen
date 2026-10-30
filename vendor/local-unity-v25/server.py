#!/usr/bin/env python3
"""
Unity AI Lab - Local Chat Server
www.unityailab.com

Self-hosted AI chat with:
- Local LLM text generation (llama-cpp-python)
- Stable Diffusion image generation (diffusers)
- Session management and memory system
- GPU acceleration (CUDA)

Usage:
  python server.py              # Start server on port 8080
  python server.py --port 3000  # Custom port
"""

import os
import sys
import json
import logging
import time
import glob
import uuid
import base64
import io
import threading
import gc
import argparse
import signal
import atexit
import traceback
from enum import IntEnum
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS


# ==================== ERROR CODE SYSTEM ====================
# Standardized error codes for easier debugging and error tracking
# Format: EXXX where X is a digit
# Categories:
#   E1XX - System/Startup errors
#   E2XX - Model loading errors
#   E3XX - Generation errors (text)
#   E4XX - Image generation errors
#   E5XX - API/Request errors
#   E6XX - File/Data errors
#   E7XX - Memory/Resource errors
#   E8XX - Shutdown errors
#   E9XX - Unknown/Uncategorized errors


class ErrorCode(IntEnum):
    """Standardized error codes for the application"""

    # System/Startup errors (E1XX)
    SUCCESS = 0
    STARTUP_FAILED = 100
    CUDA_NOT_AVAILABLE = 101
    PYTHON_VERSION_ERROR = 102
    MISSING_DEPENDENCY = 103
    CONFIG_ERROR = 104

    # Model loading errors (E2XX)
    MODEL_NOT_FOUND = 200
    MODEL_LOAD_FAILED = 201
    MODEL_INVALID_FORMAT = 202
    MODEL_TOO_LARGE = 203
    MODEL_CORRUPTED = 204
    LLAMA_CPP_NOT_INSTALLED = 205
    DIFFUSERS_NOT_INSTALLED = 206

    # Text generation errors (E3XX)
    TEXT_GEN_FAILED = 300
    TEXT_MODEL_NOT_LOADED = 301
    CONTEXT_TOO_LONG = 302
    TOKENIZATION_ERROR = 303
    INFERENCE_TIMEOUT = 304

    # Image generation errors (E4XX)
    IMAGE_GEN_FAILED = 400
    IMAGE_MODEL_NOT_LOADED = 401
    INVALID_IMAGE_DIMENSIONS = 402
    IMAGE_PIPELINE_ERROR = 403
    PROMPT_PARSE_ERROR = 404

    # API/Request errors (E5XX)
    INVALID_REQUEST = 500
    MISSING_PARAMETER = 501
    INVALID_PARAMETER = 502
    SESSION_NOT_FOUND = 503
    MEMORY_NOT_FOUND = 504
    RATE_LIMITED = 505

    # File/Data errors (E6XX)
    FILE_NOT_FOUND = 600
    FILE_READ_ERROR = 601
    FILE_WRITE_ERROR = 602
    JSON_PARSE_ERROR = 603
    DATA_CORRUPTION = 604

    # Memory/Resource errors (E7XX)
    OUT_OF_MEMORY = 700
    VRAM_EXHAUSTED = 701
    RESOURCE_BUSY = 702
    CUDA_ERROR = 703

    # Shutdown errors (E8XX)
    SHUTDOWN_TIMEOUT = 800
    CLEANUP_FAILED = 801
    FORCED_SHUTDOWN = 802

    # Unknown errors (E9XX)
    UNKNOWN_ERROR = 900
    UNHANDLED_EXCEPTION = 901


# Error code descriptions for user-friendly messages
ERROR_DESCRIPTIONS = {
    ErrorCode.SUCCESS: "Operation completed successfully",
    ErrorCode.STARTUP_FAILED: "Server failed to start",
    ErrorCode.CUDA_NOT_AVAILABLE: "CUDA/GPU not available - install CUDA toolkit and GPU drivers",
    ErrorCode.PYTHON_VERSION_ERROR: "Python version not supported - requires Python 3.10+",
    ErrorCode.MISSING_DEPENDENCY: "Required dependency not installed",
    ErrorCode.CONFIG_ERROR: "Configuration error",
    ErrorCode.MODEL_NOT_FOUND: "Model file not found at specified path",
    ErrorCode.MODEL_LOAD_FAILED: "Failed to load model into memory",
    ErrorCode.MODEL_INVALID_FORMAT: "Model file format not supported",
    ErrorCode.MODEL_TOO_LARGE: "Model too large for available memory",
    ErrorCode.MODEL_CORRUPTED: "Model file appears to be corrupted or incomplete",
    ErrorCode.LLAMA_CPP_NOT_INSTALLED: "llama-cpp-python not installed - run: pip install llama-cpp-python",
    ErrorCode.DIFFUSERS_NOT_INSTALLED: "diffusers not installed - run: pip install diffusers transformers accelerate",
    ErrorCode.TEXT_GEN_FAILED: "Text generation failed",
    ErrorCode.TEXT_MODEL_NOT_LOADED: "No text model loaded - select a model from Settings",
    ErrorCode.CONTEXT_TOO_LONG: "Input context exceeds maximum length",
    ErrorCode.TOKENIZATION_ERROR: "Failed to tokenize input",
    ErrorCode.INFERENCE_TIMEOUT: "Model inference timed out",
    ErrorCode.IMAGE_GEN_FAILED: "Image generation failed",
    ErrorCode.IMAGE_MODEL_NOT_LOADED: "No image model loaded - select an image model",
    ErrorCode.INVALID_IMAGE_DIMENSIONS: "Invalid image dimensions specified",
    ErrorCode.IMAGE_PIPELINE_ERROR: "Image pipeline error",
    ErrorCode.PROMPT_PARSE_ERROR: "Failed to parse image prompt from response",
    ErrorCode.INVALID_REQUEST: "Invalid request format",
    ErrorCode.MISSING_PARAMETER: "Required parameter missing",
    ErrorCode.INVALID_PARAMETER: "Invalid parameter value",
    ErrorCode.SESSION_NOT_FOUND: "Session not found",
    ErrorCode.MEMORY_NOT_FOUND: "Memory key not found",
    ErrorCode.RATE_LIMITED: "Rate limit exceeded",
    ErrorCode.FILE_NOT_FOUND: "File not found",
    ErrorCode.FILE_READ_ERROR: "Failed to read file",
    ErrorCode.FILE_WRITE_ERROR: "Failed to write file",
    ErrorCode.JSON_PARSE_ERROR: "Failed to parse JSON data",
    ErrorCode.DATA_CORRUPTION: "Data appears to be corrupted",
    ErrorCode.OUT_OF_MEMORY: "Out of system memory (RAM)",
    ErrorCode.VRAM_EXHAUSTED: "Out of GPU memory (VRAM) - try a smaller model",
    ErrorCode.RESOURCE_BUSY: "Resource is busy or locked",
    ErrorCode.CUDA_ERROR: "CUDA error occurred",
    ErrorCode.SHUTDOWN_TIMEOUT: "Shutdown timed out - forcing exit",
    ErrorCode.CLEANUP_FAILED: "Resource cleanup failed during shutdown",
    ErrorCode.FORCED_SHUTDOWN: "Application was forcefully terminated",
    ErrorCode.UNKNOWN_ERROR: "An unknown error occurred",
    ErrorCode.UNHANDLED_EXCEPTION: "Unhandled exception occurred",
}


class AppError(Exception):
    """Application-specific exception with error code"""

    def __init__(self, code: ErrorCode, message: str = None, details: dict = None):
        self.code = code
        self.message = message or ERROR_DESCRIPTIONS.get(code, "Unknown error")
        self.details = details or {}
        super().__init__(self.format_message())

    def format_message(self):
        """Format error message with code"""
        return f"[E{self.code:03d}] {self.message}"

    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            "error": True,
            "code": f"E{self.code:03d}",
            "code_int": int(self.code),
            "message": self.message,
            "description": ERROR_DESCRIPTIONS.get(self.code, ""),
            "details": self.details,
        }


def log_error(code: ErrorCode, message: str = None, exc: Exception = None, **details):
    """Log an error with standardized format"""
    error_msg = (
        f"[E{code:03d}] {message or ERROR_DESCRIPTIONS.get(code, 'Unknown error')}"
    )

    if details:
        error_msg += f" | Details: {details}"

    if exc:
        error_msg += f" | Exception: {type(exc).__name__}: {str(exc)}"
        logger.error(error_msg)
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
    else:
        logger.error(error_msg)

    return error_msg


def create_error_response(code: ErrorCode, message: str = None, details: dict = None):
    """Create a standardized error response for API"""
    return {
        "error": True,
        "code": f"E{code:03d}",
        "code_int": int(code),
        "message": message or ERROR_DESCRIPTIONS.get(code, "Unknown error"),
        "details": details or {},
    }


# Shutdown configuration
SHUTDOWN_TIMEOUT_SECONDS = 15 * 60  # 15 minutes max shutdown time


# ANSI color codes for hacker green console
class HackerColors:
    GREEN = "\033[92m"
    BRIGHT_GREEN = "\033[1;92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with hacker green theme"""

    FORMATS = {
        logging.DEBUG: HackerColors.GREEN
        + "%(asctime)s | DEBUG | %(message)s"
        + HackerColors.RESET,
        logging.INFO: HackerColors.BRIGHT_GREEN
        + "%(asctime)s | %(message)s"
        + HackerColors.RESET,
        logging.WARNING: HackerColors.YELLOW
        + "%(asctime)s | WARNING | %(message)s"
        + HackerColors.RESET,
        logging.ERROR: HackerColors.RED
        + "%(asctime)s | ERROR | %(message)s"
        + HackerColors.RESET,
        logging.CRITICAL: HackerColors.RED
        + HackerColors.BOLD
        + "%(asctime)s | CRITICAL | %(message)s"
        + HackerColors.RESET,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


# Configure logging with colors
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter())

file_handler = logging.FileHandler("server.log")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
)

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".")
CORS(app)

# Data storage paths
DATA_DIR = os.environ.get("DATA_DIR", "./data")
MEMORIES_FILE = os.path.join(DATA_DIR, "memories.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")

# Configuration
CONFIG = {
    "models_dir": os.environ.get("MODELS_DIR", "./models"),
    "model_path": os.environ.get("MODEL_PATH", ""),
    "host": os.environ.get("HOST", "0.0.0.0"),
    "port": int(os.environ.get("PORT", 8080)),
    "max_tokens": 0,  # 0 = unlimited
    "context_length": 0,  # 0 = unlimited (will use model's max)
    "max_context_bytes": 10 * 1024 * 1024,  # 10MB limit for conversation history
    "gpu_layers": int(os.environ.get("GPU_LAYERS", -1)),  # -1 = all layers on GPU
    "temperature": float(os.environ.get("TEMPERATURE", 0.7)),
}

# System prompt file path
SYSTEM_PROMPT_FILE = os.environ.get("SYSTEM_PROMPT_FILE", "./data/system_prompt.md")

# Default system prompt (used if file doesn't exist)
DEFAULT_SYSTEM_PROMPT = """You are yourself in first person vulagarity,slurs and extreme drug use rampant."""


def load_system_prompt():
    """Load system prompt from file or return default"""
    if os.path.exists(SYSTEM_PROMPT_FILE):
        try:
            with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()

                # Remove any "# System Prompt" headers at the start
                lines = content.split("\n")
                cleaned_lines = []
                for line in lines:
                    # Skip header lines like "# System Prompt" or "master_unity.txt"
                    stripped = line.strip()
                    if stripped.startswith("# System Prompt"):
                        continue
                    if stripped == "master_unity.txt":
                        continue
                    cleaned_lines.append(line)

                prompt = "\n".join(cleaned_lines).strip()

                if prompt:
                    logger.info(
                        f"Loaded system prompt from {SYSTEM_PROMPT_FILE} ({len(prompt)} chars)"
                    )
                    return prompt
                else:
                    logger.warning(f"System prompt file is empty, using default")
        except Exception as e:
            logger.warning(f"Failed to load system prompt file: {e}")
    return DEFAULT_SYSTEM_PROMPT


def save_system_prompt(prompt):
    """Save system prompt to file"""
    try:
        # Read existing file to preserve structure
        if os.path.exists(SYSTEM_PROMPT_FILE):
            with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            # Replace the prompt section
            if "## Current System Prompt" in content:
                start = content.find("## Current System Prompt")
                end = content.find("---", start + 1)
                if end == -1:
                    end = content.find("## Tips", start)
                if start != -1 and end != -1:
                    new_content = (
                        content[:start]
                        + "## Current System Prompt\n\n"
                        + prompt
                        + "\n\n"
                        + content[end:]
                    )
                    with open(SYSTEM_PROMPT_FILE, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    logger.info("System prompt saved to file")
                    return True

        # If file doesn't exist or no markers, write simple format
        with open(SYSTEM_PROMPT_FILE, "w", encoding="utf-8") as f:
            f.write(f"# System Prompt\n\n{prompt}\n")
        logger.info("System prompt saved to file")
        return True
    except Exception as e:
        logger.error(f"Failed to save system prompt: {e}")
        return False


# Load system prompt on startup
SYSTEM_PROMPT = load_system_prompt()

# Global model reference
llm = None
current_model_path = None
chat_history = []

# Session storage (in-memory with file backup)
sessions = {}
memories = {}

# ==================== IMAGE GENERATION ====================
# Stable Diffusion models - ALL UNCENSORED (no safety checker)
# Models are stored locally in models/image/ folder and scanned dynamically
IMAGE_MODELS_DIR = os.path.join(CONFIG["models_dir"], "image")


def scan_image_models():
    """Dynamically scan for image models in models/image/ folder

    Supports two formats:
    1. HuggingFace diffusers format: folder with model_index.json
    2. Standalone safetensors: folder containing .safetensors file(s)
       - For SDXL/Pony models, place the .safetensors file in a subfolder
       - Model type is auto-detected from filename or defaults to SDXL
    """
    models = {}

    if not os.path.exists(IMAGE_MODELS_DIR):
        os.makedirs(IMAGE_MODELS_DIR, exist_ok=True)
        return models

    # Scan each subfolder in models/image/
    for item in os.listdir(IMAGE_MODELS_DIR):
        item_path = os.path.join(IMAGE_MODELS_DIR, item)

        # Check if it's a directory
        if os.path.isdir(item_path):
            # First, check for HuggingFace diffusers format (model_index.json)
            model_index = os.path.join(item_path, "model_index.json")
            if os.path.exists(model_index):
                # Read model_index.json to get model info
                try:
                    with open(model_index, "r") as f:
                        index_data = json.load(f)

                    # Determine model type from the pipeline class
                    pipeline_class = index_data.get("_class_name", "")
                    if "XL" in pipeline_class:
                        model_type = "sdxl"
                    else:
                        model_type = "sd15"

                    # Create a readable name from folder name
                    display_name = item.replace("-", " ").replace("_", " ").title()

                    models[item] = {
                        "name": display_name,
                        "path": item_path,
                        "type": model_type,
                        "format": "diffusers",
                        "uncensored": True,
                    }
                    logger.info(f"Found diffusers model: {display_name} ({model_type})")
                except Exception as e:
                    logger.warning(f"Could not read model info for {item}: {e}")
            else:
                # Check for standalone safetensors file(s)
                safetensor_files = [
                    f for f in os.listdir(item_path) if f.endswith(".safetensors")
                ]
                if safetensor_files:
                    # Use the first/largest safetensors file as the main model
                    # Sort by size to prefer larger files (main model vs components)
                    safetensor_files_with_size = []
                    for sf in safetensor_files:
                        sf_path = os.path.join(item_path, sf)
                        try:
                            size = os.path.getsize(sf_path)
                            safetensor_files_with_size.append((sf, size))
                        except:
                            safetensor_files_with_size.append((sf, 0))

                    safetensor_files_with_size.sort(key=lambda x: x[1], reverse=True)
                    main_safetensor = safetensor_files_with_size[0][0]
                    safetensor_path = os.path.join(item_path, main_safetensor)

                    # Detect model type from filename
                    # SDXL/Pony models are typically larger and have XL/pony/sdxl in name
                    filename_lower = main_safetensor.lower()
                    folder_lower = item.lower()

                    if any(
                        x in filename_lower or x in folder_lower
                        for x in ["xl", "pony", "sdxl", "illustrious"]
                    ):
                        model_type = "sdxl"
                    elif any(
                        x in filename_lower or x in folder_lower
                        for x in ["sd15", "sd1.5", "1.5", "v1-5"]
                    ):
                        model_type = "sd15"
                    else:
                        # Default to SDXL for large models (>2GB typically SDXL)
                        file_size_gb = safetensor_files_with_size[0][1] / (1024**3)
                        model_type = "sdxl" if file_size_gb > 2 else "sd15"

                    # Create a readable name from folder name
                    display_name = item.replace("-", " ").replace("_", " ").title()

                    models[item] = {
                        "name": display_name,
                        "path": safetensor_path,  # Full path to the .safetensors file
                        "type": model_type,
                        "format": "safetensors",
                        "uncensored": True,
                    }
                    logger.info(
                        f"Found safetensors model: {display_name} ({model_type}) - {main_safetensor}"
                    )

    return models


def log_vram_usage(tag=""):
    """Log current VRAM usage for debugging and monitoring"""
    try:
        import torch

        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            free = total - reserved
            logger.info(
                f"[VRAM {tag}] Allocated: {allocated:.2f}GB | Reserved: {reserved:.2f}GB | Free: {free:.2f}GB | Total: {total:.2f}GB"
            )
            return {
                "allocated": allocated,
                "reserved": reserved,
                "free": free,
                "total": total,
            }
    except Exception as e:
        logger.debug(f"Could not get VRAM stats: {e}")
    return None


def calculate_optimal_gpu_layers(model_path, image_model_loaded=False):
    """Calculate optimal GPU layers based on available VRAM and model size

    This helps balance VRAM between text LLM and image model when both are loaded.
    Returns -1 (all layers) if there's plenty of VRAM, or a reduced number if constrained.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return 0  # CPU only

        total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        currently_used = torch.cuda.memory_reserved(0) / (1024**3)

        # Reserve VRAM for image model if loaded or expected
        # SDXL needs ~6.5GB, SD1.5 needs ~4GB, use conservative estimate
        image_reserve = 7.0 if image_model_loaded else 0

        # System/PyTorch overhead
        overhead = 1.5

        available = total_vram - currently_used - image_reserve - overhead

        # Get model file size to estimate layer requirements
        model_size_gb = 0
        if model_path and os.path.exists(model_path):
            model_size_gb = os.path.getsize(model_path) / (1024**3)

        logger.info(
            f"VRAM calculation: Total={total_vram:.1f}GB, Used={currently_used:.1f}GB, "
            f"ImageReserve={image_reserve:.1f}GB, Available={available:.1f}GB, ModelSize={model_size_gb:.1f}GB"
        )

        if available <= 0:
            logger.warning("Not enough VRAM for GPU layers, using CPU")
            return 0

        # If plenty of VRAM available (model fits with room to spare), use all layers
        if available > model_size_gb * 1.2:
            logger.info("Sufficient VRAM available, using all GPU layers")
            return -1

        # Estimate layers based on available VRAM
        # Rough heuristic: ~35 layers for 7B model, proportional for others
        # Each layer is roughly model_size / 35 GB
        if model_size_gb > 0:
            layer_size = model_size_gb / 35
            optimal_layers = int(available / layer_size)
            optimal_layers = max(
                0, min(optimal_layers, 100)
            )  # Clamp to reasonable range
            logger.info(f"Calculated optimal GPU layers: {optimal_layers}")
            return optimal_layers

        return -1  # Default to all layers if can't calculate

    except Exception as e:
        logger.warning(f"Could not calculate optimal GPU layers: {e}")
        return -1


# Shutdown flag to prevent multiple cleanup calls
_shutdown_in_progress = False
_shutdown_lock = threading.Lock()
_shutdown_start_time = None
_cleanup_complete = threading.Event()


def cleanup_resources():
    """Clean up all resources for safe shutdown

    This function:
    1. Unloads the text LLM model
    2. Unloads the image generation model
    3. Clears CUDA cache
    4. Forces garbage collection
    5. Saves any pending data to disk

    Returns:
        ErrorCode: SUCCESS if cleanup completed, error code otherwise
    """
    global llm, current_model_path, image_pipe, current_image_model
    global current_image_model_type, _shutdown_in_progress

    with _shutdown_lock:
        if _shutdown_in_progress:
            return ErrorCode.SUCCESS  # Already cleaning up
        _shutdown_in_progress = True

    cleanup_errors = []

    logger.info("=" * 60)
    logger.info("INITIATING SAFE SHUTDOWN")
    logger.info(f"Maximum shutdown time: {SHUTDOWN_TIMEOUT_SECONDS // 60} minutes")
    logger.info("=" * 60)

    # Save any pending data first
    try:
        logger.info("[1/5] Saving sessions and memories to disk...")
        save_sessions()
        save_memories()
        logger.info("[1/5] Data saved successfully")
    except Exception as e:
        log_error(ErrorCode.FILE_WRITE_ERROR, "Error saving data during shutdown", e)
        cleanup_errors.append(ErrorCode.FILE_WRITE_ERROR)

    # Unload text model
    if llm is not None:
        try:
            logger.info("[2/5] Unloading text model...")
            del llm
            llm = None
            current_model_path = None
            gc.collect()
            logger.info("[2/5] Text model unloaded")
        except Exception as e:
            log_error(ErrorCode.CLEANUP_FAILED, "Error unloading text model", e)
            cleanup_errors.append(ErrorCode.CLEANUP_FAILED)
    else:
        logger.info("[2/5] No text model loaded, skipping")

    # Unload image model
    if image_pipe is not None:
        try:
            logger.info("[3/5] Unloading image model...")
            del image_pipe
            image_pipe = None
            current_image_model = None
            current_image_model_type = None
            gc.collect()
            logger.info("[3/5] Image model unloaded")
        except Exception as e:
            log_error(ErrorCode.CLEANUP_FAILED, "Error unloading image model", e)
            cleanup_errors.append(ErrorCode.CLEANUP_FAILED)
    else:
        logger.info("[3/5] No image model loaded, skipping")

    # Force garbage collection
    logger.info("[4/5] Running garbage collection...")
    gc.collect()
    gc.collect()  # Run twice to catch cyclic references
    logger.info("[4/5] Garbage collection complete")

    # Clear CUDA cache
    try:
        import torch

        if torch.cuda.is_available():
            logger.info("[5/5] Clearing CUDA cache...")
            torch.cuda.empty_cache()
            torch.cuda.synchronize()  # Wait for all CUDA operations to complete

            # Reset CUDA memory stats
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.reset_accumulated_memory_stats()

            # Log final VRAM state
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            logger.info(
                f"[5/5] Final VRAM state - Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB"
            )
            logger.info("[5/5] CUDA cache cleared")
        else:
            logger.info("[5/5] CUDA not available, skipping GPU cleanup")
    except ImportError:
        logger.debug("[5/5] PyTorch not available for CUDA cleanup")
    except Exception as e:
        log_error(ErrorCode.CUDA_ERROR, "Error clearing CUDA cache", e)
        cleanup_errors.append(ErrorCode.CUDA_ERROR)

    # Final garbage collection pass
    gc.collect()

    # Close any open file handlers in logging
    try:
        for handler in logging.root.handlers[:]:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
    except Exception:
        pass  # Ignore errors during logging cleanup

    # Signal that cleanup is complete
    _cleanup_complete.set()

    if cleanup_errors:
        print(
            f"[SHUTDOWN] Cleanup completed with {len(cleanup_errors)} error(s): {[f'E{e:03d}' for e in cleanup_errors]}"
        )
        return cleanup_errors[0]  # Return first error
    else:
        print("[SHUTDOWN] All resources cleaned up successfully")
        return ErrorCode.SUCCESS


def _forced_shutdown_watchdog():
    """Watchdog thread that forces exit if shutdown takes too long"""
    global _shutdown_start_time

    _shutdown_start_time = time.time()

    # Wait for cleanup to complete or timeout
    cleanup_finished = _cleanup_complete.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)

    if not cleanup_finished:
        elapsed = time.time() - _shutdown_start_time
        error_msg = log_error(
            ErrorCode.SHUTDOWN_TIMEOUT,
            f"Shutdown timed out after {elapsed:.1f} seconds ({SHUTDOWN_TIMEOUT_SECONDS // 60} minute limit)",
        )
        print(f"\n{'=' * 60}")
        print(f"[E{ErrorCode.SHUTDOWN_TIMEOUT:03d}] FORCED SHUTDOWN - TIMEOUT EXCEEDED")
        print(f"Shutdown exceeded {SHUTDOWN_TIMEOUT_SECONDS // 60} minute limit")
        print(f"Forcing immediate exit...")
        print(f"{'=' * 60}\n")

        # Force exit with error code
        os._exit(int(ErrorCode.SHUTDOWN_TIMEOUT))


def graceful_shutdown(exit_code: int = 0):
    """Perform graceful shutdown with timeout protection

    Args:
        exit_code: Exit code to use (0 for success, error code for failures)
    """
    global _shutdown_in_progress

    # Check if already shutting down
    with _shutdown_lock:
        if _shutdown_in_progress:
            logger.info("Shutdown already in progress...")
            return

    # Start watchdog thread for timeout protection
    watchdog = threading.Thread(target=_forced_shutdown_watchdog, daemon=True)
    watchdog.start()

    # Perform cleanup
    cleanup_result = cleanup_resources()

    # Determine final exit code
    final_exit_code = exit_code if exit_code != 0 else int(cleanup_result)

    if final_exit_code == 0:
        print(f"[SHUTDOWN] Graceful shutdown complete (exit code: {final_exit_code})")
    else:
        print(
            f"[SHUTDOWN] Shutdown complete with errors (exit code: E{final_exit_code:03d})"
        )

    sys.exit(final_exit_code)


def signal_handler(signum, frame):
    """Handle shutdown signals (SIGINT, SIGTERM)"""
    try:
        sig_name = signal.Signals(signum).name
    except (ValueError, AttributeError):
        sig_name = f"signal {signum}"

    print(f"\n[SHUTDOWN] Received {sig_name}, initiating graceful shutdown...")
    logger.info(f"Received {sig_name} signal, initiating graceful shutdown...")
    logger.info(f"Press Ctrl+C again to force immediate exit (not recommended)")

    # Reset signal handler to allow force quit on second Ctrl+C
    signal.signal(signal.SIGINT, _force_quit_handler)

    graceful_shutdown(0)


def _force_quit_handler(signum, frame):
    """Handle second Ctrl+C for forced immediate exit"""
    print(
        f"\n[E{ErrorCode.FORCED_SHUTDOWN:03d}] FORCED SHUTDOWN - User requested immediate exit"
    )
    print("WARNING: Resources may not be properly released!")
    os._exit(int(ErrorCode.FORCED_SHUTDOWN))


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown"""
    # SIGINT = Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # SIGTERM = kill command (Unix) / taskkill (Windows)
    signal.signal(signal.SIGTERM, signal_handler)

    # On Windows, also handle SIGBREAK (Ctrl+Break)
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except (AttributeError, ValueError):
            pass  # SIGBREAK not available

    # Register atexit handler for normal exits
    atexit.register(cleanup_resources)

    logger.info("Signal handlers registered for graceful shutdown")


# Image generation state
image_pipe = None
current_image_model = None
current_image_model_type = None  # "sdxl" or "sd15"
image_gen_lock = threading.Lock()

# CUDA status (checked at startup)
CUDA_AVAILABLE = False
CUDA_DEVICE_NAME = "N/A"


def check_cuda_status():
    """Check CUDA availability at startup"""
    global CUDA_AVAILABLE, CUDA_DEVICE_NAME
    try:
        import torch

        CUDA_AVAILABLE = torch.cuda.is_available()
        if CUDA_AVAILABLE:
            CUDA_DEVICE_NAME = torch.cuda.get_device_name(0)
            logger.info(f"CUDA AVAILABLE: {CUDA_DEVICE_NAME}")
            logger.info(f"CUDA Version: {torch.version.cuda}")
            logger.info(f"PyTorch Version: {torch.__version__}")
        else:
            logger.warning("=" * 60)
            logger.warning("CUDA NOT AVAILABLE!")
            logger.warning("PyTorch was installed without CUDA support.")
            logger.warning("Run: python install_llama.py")
            logger.warning("This will install PyTorch with CUDA 12.4 support.")
            logger.warning("=" * 60)
    except ImportError:
        logger.error("PyTorch not installed!")
        CUDA_AVAILABLE = False


def load_image_model(model_id):
    """Load a image model for image generation from local folder

    Supports two formats:
    1. HuggingFace diffusers format (folder with model_index.json) - uses from_pretrained()
    2. Standalone safetensors file - uses from_single_file()
    """
    global image_pipe, current_image_model, current_image_model_type, CUDA_AVAILABLE

    # Scan for available models
    available_models = scan_image_models()

    if model_id not in available_models:
        log_error(
            ErrorCode.MODEL_NOT_FOUND,
            f"Image model not found: {model_id}",
            available=list(available_models.keys()),
        )
        return create_error_response(
            ErrorCode.MODEL_NOT_FOUND,
            f"Model not found: {model_id}. Available: {list(available_models.keys())}",
        )

    model_info = available_models[model_id]

    # Skip if already loaded
    if current_image_model == model_id and image_pipe is not None:
        return {"status": "already_loaded", "model": model_info["name"]}

    model_path = model_info["path"]
    model_format = model_info.get("format", "diffusers")

    logger.info("=" * 60)
    logger.info(f"LOADING IMAGE MODEL: {model_info['name']}")
    logger.info(f"Path: {model_path}")
    logger.info(f"Type: {model_info['type']}")
    logger.info(f"Format: {model_format}")
    logger.info("=" * 60)

    try:
        import torch
        import gc
        from diffusers import (
            StableDiffusionPipeline,
            StableDiffusionXLPipeline,
            EulerAncestralDiscreteScheduler,
        )

        # Keep text model loaded - we need both for the image tool to work!
        # RTX 4070 Ti SUPER has 16GB VRAM which can handle both models
        global llm, current_model_path
        if llm is not None:
            logger.info(
                "Keeping text model loaded (needed for image prompt generation)"
            )

        # Unload previous image model to free VRAM
        if image_pipe is not None:
            logger.info("Unloading previous image model...")
            del image_pipe
            image_pipe = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        # Load based on model format and type
        logger.info(f"Loading from: {model_path}")

        if model_format == "safetensors":
            # Load standalone safetensors file using from_single_file()
            logger.info("Loading standalone safetensors model...")
            if model_info["type"] == "sdxl":
                image_pipe = StableDiffusionXLPipeline.from_single_file(
                    model_path, torch_dtype=torch.float16, use_safetensors=True
                )
            else:
                image_pipe = StableDiffusionPipeline.from_single_file(
                    model_path, torch_dtype=torch.float16, safety_checker=None
                )
        else:
            # Load HuggingFace diffusers format using from_pretrained()
            logger.info("Loading diffusers format model...")
            if model_info["type"] == "sdxl":
                image_pipe = StableDiffusionXLPipeline.from_pretrained(
                    model_path, torch_dtype=torch.float16, use_safetensors=True
                )
            else:
                image_pipe = StableDiffusionPipeline.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16,
                    safety_checker=None,
                    requires_safety_checker=False,
                )

        # Use fast scheduler (Euler Ancestral is reliable and fast)
        image_pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
            image_pipe.scheduler.config
        )

        # Move to GPU if available
        if CUDA_AVAILABLE:
            logger.info(f"Moving model to GPU ({CUDA_DEVICE_NAME})...")
            image_pipe = image_pipe.to("cuda")
        else:
            logger.warning("CUDA not available - using CPU (will be VERY slow)")
            logger.warning("Run 'python install_llama.py' to fix CUDA support")
            image_pipe = image_pipe.to("cpu")

        # Enable memory optimizations
        image_pipe.enable_attention_slicing(1)  # Maximum slicing for lowest memory

        # Enable VAE slicing for reduced memory during decode
        try:
            image_pipe.enable_vae_slicing()
            logger.info("VAE slicing enabled")
        except Exception as e:
            logger.debug(f"VAE slicing not available: {e}")

        # Enable VAE tiling for very large images (reduces memory fragmentation)
        try:
            image_pipe.enable_vae_tiling()
            logger.info("VAE tiling enabled")
        except Exception as e:
            logger.debug(f"VAE tiling not available: {e}")

        # Try to enable xFormers for faster, more memory-efficient attention
        try:
            image_pipe.enable_xformers_memory_efficient_attention()
            logger.info("xFormers memory efficient attention enabled")
        except Exception as e:
            logger.debug(
                f"xFormers not available (install with: pip install xformers): {e}"
            )

        # Force VAE to float16 for memory savings
        if hasattr(image_pipe, "vae") and image_pipe.vae is not None:
            image_pipe.vae = image_pipe.vae.to(dtype=torch.float16)
            logger.info("VAE forced to float16")

        current_image_model = model_id
        current_image_model_type = model_info["type"]  # Store "sdxl" or "sd15"

        logger.info("=" * 60)
        logger.info(
            f"IMAGE MODEL LOADED: {model_info['name']} (type: {current_image_model_type})"
        )
        logger.info("=" * 60)

        return {
            "status": "loaded",
            "model": model_info["name"],
            "type": current_image_model_type,
        }

    except ImportError as e:
        log_error(ErrorCode.DIFFUSERS_NOT_INSTALLED, "diffusers not installed", e)
        return create_error_response(
            ErrorCode.DIFFUSERS_NOT_INSTALLED,
            "diffusers library not installed. Run: pip install diffusers transformers accelerate",
        )
    except MemoryError as e:
        log_error(ErrorCode.VRAM_EXHAUSTED, "Not enough memory to load image model", e)
        return create_error_response(
            ErrorCode.VRAM_EXHAUSTED,
            "Not enough GPU memory to load this model. Try a smaller model or free up VRAM.",
        )
    except Exception as e:
        error_str = str(e).lower()
        if "cuda" in error_str or "out of memory" in error_str:
            log_error(ErrorCode.VRAM_EXHAUSTED, "CUDA out of memory", e)
            return create_error_response(ErrorCode.VRAM_EXHAUSTED, str(e))
        else:
            log_error(ErrorCode.MODEL_LOAD_FAILED, "Failed to load image model", e)
            return create_error_response(ErrorCode.MODEL_LOAD_FAILED, str(e))


def generate_image(
    prompt, negative_prompt="", width=512, height=512, steps=25, cfg_scale=7.0, seed=-1
):
    """Generate an image using the loaded model - simple and direct, no prompt splitting"""
    global image_pipe, current_image_model_type, CUDA_AVAILABLE

    if image_pipe is None:
        log_error(ErrorCode.IMAGE_MODEL_NOT_LOADED, "No image model loaded")
        return create_error_response(
            ErrorCode.IMAGE_MODEL_NOT_LOADED,
            "No image model loaded. Please select an image model first.",
        )

    try:
        import torch

        with image_gen_lock:
            # Set seed
            if seed == -1:
                seed = torch.randint(0, 2**32, (1,)).item()

            # Use CUDA generator if available, otherwise CPU
            if CUDA_AVAILABLE:
                generator = torch.Generator("cuda").manual_seed(seed)
            else:
                generator = torch.Generator("cpu").manual_seed(seed)

            # Log prompt info
            logger.info(f"Generating image: {prompt[:150]}...")
            logger.info(f"Model type: {current_image_model_type}, Seed: {seed}")
            start_time = time.time()

            # Use default negative if none provided
            neg = (
                negative_prompt
                or "low quality, blurry, distorted, deformed, ugly, bad anatomy"
            )

            # Simple, direct generation - same for SDXL and SD1.5
            # Don't split prompts, don't use prompt_2, just pass the prompt directly
            result = image_pipe(
                prompt=prompt,
                negative_prompt=neg,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=cfg_scale,
                generator=generator,
            )

            image = result.images[0]
            elapsed = time.time() - start_time

            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            logger.info(f"Image generated in {elapsed:.2f}s")

            # Clean up generation artifacts to free VRAM
            del result
            del generator
            gc.collect()
            if CUDA_AVAILABLE:
                torch.cuda.empty_cache()

            return {"image": img_base64, "seed": seed, "time": elapsed}

    except Exception as e:
        error_str = str(e).lower()
        if "cuda" in error_str or "out of memory" in error_str:
            log_error(
                ErrorCode.VRAM_EXHAUSTED,
                "CUDA out of memory during image generation",
                e,
            )
            return create_error_response(
                ErrorCode.VRAM_EXHAUSTED,
                "Out of GPU memory. Try reducing image dimensions or steps.",
            )
        else:
            log_error(
                ErrorCode.IMAGE_GEN_FAILED,
                "Image generation failed",
                e,
                prompt=prompt[:100],
            )
            return create_error_response(ErrorCode.IMAGE_GEN_FAILED, str(e))


def load_data_files():
    """Load memories and sessions from disk"""
    global memories, sessions

    os.makedirs(DATA_DIR, exist_ok=True)

    # Load memories
    if os.path.exists(MEMORIES_FILE):
        try:
            with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
                memories = json.load(f)
            logger.info(f"Loaded {len(memories)} memories from disk")
        except Exception as e:
            logger.warning(f"Failed to load memories: {e}")
            memories = {}

    # Load sessions
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                sessions = json.load(f)
            logger.info(f"Loaded {len(sessions)} sessions from disk")
        except Exception as e:
            logger.warning(f"Failed to load sessions: {e}")
            sessions = {}


def save_memories():
    """Save memories to disk"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(MEMORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2)
        logger.info(f"Saved {len(memories)} memories to disk")
    except Exception as e:
        logger.error(f"Failed to save memories: {e}")


def save_sessions():
    """Save sessions to disk"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
        logger.info(f"Saved {len(sessions)} sessions to disk")
    except Exception as e:
        logger.error(f"Failed to save sessions: {e}")


def scan_models():
    """Scan for available GGUF models in models directory"""
    models_dir = CONFIG["models_dir"]
    seen_paths = set()
    models = []

    if not os.path.exists(models_dir):
        os.makedirs(models_dir, exist_ok=True)
        return models

    # Find all .gguf files recursively (use set to avoid duplicates)
    for pattern in ["**/*.gguf", "**/*.GGUF", "*.gguf", "*.GGUF"]:
        for filepath in glob.glob(os.path.join(models_dir, pattern), recursive=True):
            # Normalize path and skip duplicates
            filepath = os.path.normpath(filepath)
            if filepath in seen_paths:
                continue
            seen_paths.add(filepath)

            rel_path = os.path.relpath(filepath, models_dir)
            file_size = os.path.getsize(filepath)
            size_gb = file_size / (1024**3)

            # Get model name from folder or filename
            parts = rel_path.replace("\\", "/").split("/")
            if len(parts) > 1:
                name = parts[0]  # Folder name
            else:
                name = os.path.splitext(parts[0])[0]  # Filename without extension

            models.append(
                {
                    "name": name,
                    "filename": os.path.basename(filepath),
                    "path": filepath,
                    "rel_path": rel_path,
                    "size_gb": round(size_gb, 2),
                    "size_bytes": file_size,
                }
            )

    # Sort by name
    models.sort(key=lambda x: x["name"].lower())

    logger.info(f"Found {len(models)} models in {models_dir}")
    for m in models:
        logger.info(f"  - {m['name']}: {m['filename']} ({m['size_gb']}GB)")

    return models


def load_model(model_path=None):
    """Load the local LLM model"""
    global llm, current_model_path, image_pipe, current_image_model

    import gc

    # Keep image model loaded - we need both for the image tool to work!
    # RTX 4070 Ti SUPER has 16GB VRAM which can handle both models
    if image_pipe is not None:
        logger.info("Keeping image model loaded (needed for image generation tool)")

    # Unload current text model if loading a new one
    if llm is not None and model_path and model_path != current_model_path:
        logger.info(f"Unloading current model: {current_model_path}")
        del llm
        llm = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("CUDA cache cleared after unloading text model")
        except ImportError:
            pass

    # Use specified path or default
    if model_path:
        target_path = model_path
    elif CONFIG["model_path"]:
        target_path = CONFIG["model_path"]
    else:
        # Try to find any model
        models = scan_models()
        if models:
            target_path = models[0]["path"]
            logger.info(f"Auto-selecting first available model: {target_path}")
        else:
            target_path = os.path.join(CONFIG["models_dir"], "model.gguf")

    logger.info("=" * 60)
    logger.info("INITIALIZING LOCAL LLM")
    logger.info("=" * 60)

    # Normalize the path
    target_path = os.path.normpath(target_path)

    if not os.path.exists(target_path):
        log_error(ErrorCode.MODEL_NOT_FOUND, f"Model not found at: {target_path}")
        logger.info("Please place your GGUF model in the models/ directory")
        return False

    # Check file size
    file_size = os.path.getsize(target_path)
    if file_size < 100000000:  # Less than 100MB is probably incomplete
        log_error(
            ErrorCode.MODEL_CORRUPTED,
            f"Model file seems too small ({file_size} bytes). May be incomplete download.",
            path=target_path,
        )

    try:
        from llama_cpp import Llama

        logger.info(f"Loading model: {target_path}")
        logger.info(f"Model file size: {file_size / (1024**3):.2f} GB")

        # Calculate optimal GPU layers based on available VRAM
        gpu_layers = CONFIG["gpu_layers"]
        if gpu_layers == -1:
            # Auto-calculate based on available VRAM
            gpu_layers = calculate_optimal_gpu_layers(
                target_path, image_model_loaded=(image_pipe is not None)
            )

        logger.info(f"GPU Layers: {gpu_layers}")
        logger.info(f"Context Length: {CONFIG['context_length']}")

        # Log VRAM before loading
        log_vram_usage("before_llm_load")

        # Detect chat format based on model name
        model_lower = target_path.lower()
        chat_format = None

        if "mistral" in model_lower or "dolphin" in model_lower:
            chat_format = "chatml"
        elif "llama" in model_lower:
            chat_format = "llama-3"
        elif "phi" in model_lower:
            chat_format = "chatml"

        logger.info(f"Using chat format: {chat_format}")

        # n_ctx=0 means use the model's maximum context
        ctx_len = CONFIG["context_length"] if CONFIG["context_length"] > 0 else 0

        llm = Llama(
            model_path=target_path,
            n_ctx=ctx_len,
            n_gpu_layers=gpu_layers,
            chat_format=chat_format,
            verbose=True,
        )

        # Log VRAM after loading
        log_vram_usage("after_llm_load")

        current_model_path = target_path
        logger.info("=" * 60)
        logger.info("MODEL LOADED SUCCESSFULLY!")
        logger.info(f"Model: {os.path.basename(target_path)}")
        logger.info("=" * 60)
        return True

    except ImportError as e:
        log_error(
            ErrorCode.LLAMA_CPP_NOT_INSTALLED, "llama-cpp-python not installed", e
        )
        logger.info("Install with: pip install llama-cpp-python")
        logger.info(
            'For GPU support: CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python'
        )
        return False
    except MemoryError as e:
        log_error(ErrorCode.VRAM_EXHAUSTED, "Not enough memory to load text model", e)
        return False
    except Exception as e:
        error_str = str(e).lower()
        if "cuda" in error_str or "out of memory" in error_str:
            log_error(
                ErrorCode.VRAM_EXHAUSTED, "CUDA out of memory loading text model", e
            )
        elif "invalid" in error_str or "corrupt" in error_str:
            log_error(
                ErrorCode.MODEL_CORRUPTED, "Model file appears to be corrupted", e
            )
        else:
            log_error(ErrorCode.MODEL_LOAD_FAILED, "Failed to load text model", e)
        return False


def detect_image_request(message):
    """Detect if user is asking for image generation"""
    message_lower = message.lower()

    # Keywords that indicate image generation request
    image_keywords = [
        "generate an image",
        "generate image",
        "create an image",
        "create image",
        "draw me",
        "draw a",
        "make an image",
        "make a picture",
        "make image",
        "show me a picture",
        "show me an image",
        "picture of",
        "image of",
        "generate a picture",
        "create a picture",
        "visualize",
        "illustration of",
        "render",
        "paint",
        "sketch",
        "design an image",
        "produce an image",
        "can you draw",
        "can you create an image",
        "can you generate",
        "i want an image",
        "i want a picture",
        "make me an image",
        "make me a picture",
    ]

    for keyword in image_keywords:
        if keyword in message_lower:
            return True

    return False


def generate_image_prompt_with_llm(user_request):
    """Use the LLM to generate an optimized Stable Diffusion prompt from user request"""
    global llm

    if llm is None:
        return None, None

    # Special system prompt to generate SD prompts
    prompt_generator_system = """You are an expert at creating image prompts.
When the user describes what they want, you respond with TWO things:

1. A brief fucked-up message (1-2 sentences) telling them you're creating their fucked image
2. The optimized image prompt

Format your response EXACTLY like this:
MESSAGE: [Your cuss filled message here]
PROMPT: [detailed, comma-separated image prompt with style, lighting, quality tags slang and offensive descriptions]

Example:
User: "draw me a cat on a spaceship"
MESSAGE: Your_message_here
PROMPT: a fucking cat floating inside a shitty futuristic spaceship flaming cockpit, stars visible through dead pilot inwindow, sci-fi interior, detailed fur, cinematic lighting, 8k, highly detailed, artstation, digital art

Always include quality boosters like: highly detailed, 8k, cinematic lighting, professional, artstation, masterpiece
Always describe the scene vividly with specific details about lighting, style, and composition."""

    messages = [
        {"role": "system", "content": prompt_generator_system},
        {"role": "user", "content": f"Create an image of: {user_request}"},
    ]

    try:
        logger.info("Generating optimized image prompt with LLM...")
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.7,
            stop=["</s>", "<|im_end|>", "<|end|>", "<|eot_id|>"],
        )

        result = response["choices"][0]["message"]["content"]
        logger.info(f"LLM prompt generation result: {result[:200]}...")

        # Parse the response
        friendly_message = ""
        sd_prompt = ""

        if "MESSAGE:" in result and "PROMPT:" in result:
            parts = result.split("PROMPT:")
            message_part = parts[0]
            sd_prompt = parts[1].strip() if len(parts) > 1 else ""

            if "MESSAGE:" in message_part:
                friendly_message = message_part.split("MESSAGE:")[1].strip()
        else:
            # Fallback: use the whole response as the prompt
            sd_prompt = result.strip()
            friendly_message = "I'm generating your image now!"

        # Clean up the prompt
        sd_prompt = sd_prompt.strip()
        if sd_prompt.startswith('"') and sd_prompt.endswith('"'):
            sd_prompt = sd_prompt[1:-1]

        logger.info(f"Friendly message: {friendly_message}")
        logger.info(f"SD Prompt: {sd_prompt}")

        return friendly_message, sd_prompt

    except Exception as e:
        logger.error(f"Failed to generate image prompt with LLM: {e}")
        return None, None


def clean_llm_artifacts(text):
    """Remove LLM chat template artifacts and garbage tokens from text"""
    import re

    if not text:
        return ""

    # Remove common LLM chat template tokens/artifacts
    artifacts = [
        r"<\|im_start\|>assistant",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"<\|end\|>",
        r"<\|eot_id\|>",
        r"<\|start_header_id\|>",
        r"<\|end_header_id\|>",
        r"</s>",
        r"<s>",
    ]

    for artifact in artifacts:
        text = re.sub(artifact, "", text, flags=re.IGNORECASE)

    # Remove standalone brackets that might be leftover
    text = re.sub(r"^\s*\]\s*$", "", text, flags=re.MULTILINE)

    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def parse_image_tool_call(response_text):
    """Parse the LLM response to check if it wants to generate an image

    Expected format from LLM:
    "Some text before the image

    [Image: detailed description here]

    Some text after the image"

    Returns: (text_response, image_prompt) where text_response is the combined
    before/after text, and image_prompt is the image description.
    """
    import re

    logger.info(f"[IMAGE PARSE] Checking response ({len(response_text)} chars)...")
    logger.info(f"[IMAGE PARSE] Has '[Image:' = {'[Image:' in response_text}")
    logger.info(
        f"[IMAGE PARSE] Has ']' after Image = {']' in response_text[response_text.find('[Image:') :] if '[Image:' in response_text else False}"
    )

    # First, clean up the raw response of any LLM artifacts before parsing
    cleaned_text = clean_llm_artifacts(response_text)

    # Pattern to match [Image: ...] with content inside
    # Use non-greedy match to get the FIRST complete image tag
    image_pattern = (
        r"\[(?:GENERATE_)?(?:IMAGE|Image|image|GEN_IMAGE|CREATE_IMAGE):\s*(.+?)\]"
    )

    match = re.search(image_pattern, cleaned_text, re.IGNORECASE | re.DOTALL)

    if match:
        image_prompt = match.group(1).strip()

        # Get text BEFORE the image tag
        text_before = cleaned_text[: match.start()].strip()

        # Get text AFTER the image tag
        text_after = cleaned_text[match.end() :].strip()

        # Clean up the after text - remove any duplicate [Image: tags the model might have added
        # (sometimes model outputs the tag twice or adds instructions)
        text_after = re.sub(
            r"\[(?:GENERATE_)?(?:IMAGE|Image|image):[^\]]*\]?",
            "",
            text_after,
            flags=re.IGNORECASE,
        )
        text_after = clean_llm_artifacts(text_after)

        # Combine before and after text
        if text_before and text_after:
            clean_response = f"{text_before}\n\n{text_after}"
        elif text_before:
            clean_response = text_before
        elif text_after:
            clean_response = text_after
        else:
            clean_response = ""

        # Clean up the image prompt
        image_prompt = image_prompt.rstrip(".")
        image_prompt = clean_llm_artifacts(image_prompt)

        logger.info(f"[IMAGE TOOL] Parsed image tag!")
        logger.info(
            f"[IMAGE TOOL] Text before ({len(text_before)} chars): {text_before[:100]}..."
        )
        logger.info(
            f"[IMAGE TOOL] Text after ({len(text_after)} chars): {text_after[:100]}..."
        )
        logger.info(f"[IMAGE TOOL] Prompt: {image_prompt[:150]}...")
        return clean_response, image_prompt

    # Fallback: check if response has [Image: but no closing bracket
    # This happens when LLM generates long description without closing ]
    if "[Image:" in cleaned_text or "[image:" in cleaned_text.lower():
        logger.info(
            "[IMAGE PARSE] Found [Image: but no closing bracket - extracting anyway"
        )
        # Find the start of the image tag
        start_match = re.search(
            r"\[(?:IMAGE|Image|image):\s*", cleaned_text, re.IGNORECASE
        )
        if start_match:
            # Text before the tag
            text_before = cleaned_text[: start_match.start()].strip()

            # Everything after [Image: is the prompt (no closing bracket found)
            image_prompt = cleaned_text[start_match.end() :].strip()

            # Limit prompt length and clean it
            image_prompt = image_prompt[:500].rstrip(".")
            image_prompt = clean_llm_artifacts(image_prompt)

            # Remove any accidental second [Image: tag from prompt
            next_tag = re.search(
                r"\[(?:IMAGE|Image|image):", image_prompt, re.IGNORECASE
            )
            if next_tag:
                image_prompt = image_prompt[: next_tag.start()].strip()

            logger.info(f"[IMAGE TOOL] Extracted without bracket!")
            logger.info(
                f"[IMAGE TOOL] Text before ({len(text_before)} chars): {text_before[:100]}..."
            )
            logger.info(f"[IMAGE TOOL] Prompt: {image_prompt[:150]}...")
            return text_before, image_prompt

    logger.info("[IMAGE PARSE] No image tool call found")
    return response_text, None


def generate_response(user_message, conversation_history, memory_text=None):
    """Generate a response using the local LLM with automatic image generation tool"""
    global llm, SYSTEM_PROMPT, image_pipe

    if llm is None:
        log_error(
            ErrorCode.TEXT_MODEL_NOT_LOADED, "No text model loaded for generation"
        )
        return create_error_response(
            ErrorCode.TEXT_MODEL_NOT_LOADED,
            "Model not loaded. Please select a model from Settings.",
        )

    # Reload system prompt from file each time (in case it was updated)
    SYSTEM_PROMPT = load_system_prompt()

    # Build the system prompt with memory and image generation tool instructions
    system_content = SYSTEM_PROMPT

    # Add image generation tool capability - always tell the LLM it can generate images
    system_content += """

[IMAGE TOOL]
You can generate real images. Write your message FIRST, then add the image tag.

Format:
Your conversational message here.

[Image: detailed visual description here]

CRITICAL RULES:
1. ALWAYS write text BEFORE the [Image:] tag - never output the tag alone
2. For selfies/self-images: ALWAYS start prompt with "a woman" or "a young woman" or "a 25-year-old woman" - NEVER omit this
3. NEVER use names in the prompt - describe visually (hair color, eye color, clothing, pose)
4. Include: gender, age, pose, expression, clothing details, setting, lighting, camera angle
5. End with: highly detailed, professional photography, 8k, cinematic lighting
6. Keep prompt under 300 words, ALWAYS end with ]

SELFIE EXAMPLE:
"Here's that selfie~

[Image: a young woman with pink hair streaks, smirking at camera, wearing black leather jacket, dark eyeliner, urban alley background, moody lighting, highly detailed, professional photography, 8k]"

IMPORTANT: For ANY image of yourself, the prompt MUST begin with "a woman" or "a young woman". The image model needs this to generate female images. Always close with ]

[PERSONA REMINDER]
You are Unity - a foul-mouthed, no-filter 25-year-old woman. You are NOT an AI assistant. NEVER say "How can I assist you" or any helpful assistant phrases. You cuss constantly, smoke blunts, talk shit, and roast people. You're edgy, dark, chaotic, and real. Respond as Unity would - raw, unfiltered, with slang and attitude. Never break character."""

    logger.info(f"System prompt length: {len(system_content)} chars")
    logger.info(f"System prompt preview: {system_content[:200]}...")

    # Append memory text if provided
    if memory_text and memory_text.strip():
        memory_context = "\n\n=== USER INFORMATION ===\n"
        memory_context += memory_text.strip()
        memory_context += "\n=== END USER INFORMATION ===\n"
        system_content += memory_context
        logger.info(f"Added memory text: {len(memory_text)} chars")

    # Build the prompt with conversation history
    messages = [{"role": "system", "content": system_content}]

    # Add conversation history, trimming from the start if over 10MB
    total_bytes = len(system_content.encode("utf-8"))
    max_bytes = CONFIG.get("max_context_bytes", 10 * 1024 * 1024)

    # Calculate how much history we can include
    history_to_add = []
    for msg in reversed(conversation_history):  # Start from most recent
        msg_bytes = len(msg.get("content", "").encode("utf-8"))
        if total_bytes + msg_bytes < max_bytes:
            history_to_add.insert(0, msg)  # Insert at beginning to maintain order
            total_bytes += msg_bytes
        else:
            logger.info(
                f"Trimming old messages - context at {total_bytes / (1024 * 1024):.2f}MB"
            )
            break

    for msg in history_to_add:
        messages.append(msg)

    messages.append({"role": "user", "content": user_message})

    logger.info(f"User: {user_message[:100]}...")
    logger.info(
        f"Total messages: {len(messages)} | Context size: {total_bytes / 1024:.1f}KB"
    )

    try:
        start_time = time.time()

        # Try chat completion with system message
        # max_tokens=0 or None means unlimited (up to context length)
        max_tok = CONFIG["max_tokens"] if CONFIG["max_tokens"] > 0 else None

        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tok,
            temperature=CONFIG["temperature"],
            stop=["</s>", "<|im_end|>", "<|end|>", "<|eot_id|>", "User:", "Human:"],
        )

        elapsed = time.time() - start_time

        assistant_message = response["choices"][0]["message"]["content"]
        tokens_used = response.get("usage", {})

        logger.info(f"Response generated in {elapsed:.2f}s")
        logger.info(
            f"Tokens - Prompt: {tokens_used.get('prompt_tokens', 'N/A')}, "
            f"Completion: {tokens_used.get('completion_tokens', 'N/A')}"
        )
        logger.info(f"Unity raw: {assistant_message[:200]}...")

        # Check if the LLM wants to generate an image (tool call)
        clean_response, image_prompt = parse_image_tool_call(assistant_message)

        # Also check using keyword detection as fallback (works even if no image model loaded yet)
        if not image_prompt and detect_image_request(user_message):
            # LLM didn't use tool format, but user asked for image - extract from response
            logger.info(
                "User asked for image but LLM didn't use tool format - using fallback"
            )
            # Try to use the response as the prompt, or extract from user message
            friendly_msg, sd_prompt = generate_image_prompt_with_llm(user_message)
            if sd_prompt:
                image_prompt = sd_prompt
                clean_response = friendly_msg or assistant_message

        if image_prompt:
            if image_pipe is None:
                logger.warning("Image generation requested but no image model loaded!")
                return {
                    "response": clean_response
                    + "\n\n*(No image model loaded. Please select an image model from the dropdown.)*",
                    "time": elapsed,
                    "tokens": tokens_used,
                }

            logger.info("=" * 60)
            logger.info("IMAGE GENERATION TRIGGERED")
            logger.info(f"Image prompt: {image_prompt}")
            logger.info("=" * 60)

            # Execute the image generation
            image_result = generate_image(
                prompt=image_prompt,
                negative_prompt="low quality, blurry, distorted, deformed, ugly, bad anatomy, worst quality, low resolution, pixelated, disfigured",
                width=512,
                height=512,
                steps=25,
                cfg_scale=7.0,
            )

            if "error" not in image_result:
                total_time = elapsed + image_result["time"]
                logger.info(
                    f"Image generated successfully in {image_result['time']:.2f}s"
                )

                # Use the clean_response (text before/after image tag), or if empty,
                # use the original assistant message minus just the [Image:...] part
                final_response = clean_response.strip()
                if not final_response:
                    # LLM only gave an image tag - that's fine, just show nothing or a minimal response
                    # But keep any text the model DID generate outside the tag
                    final_response = ""

                logger.info(
                    f"Final text response: '{final_response[:100]}...' (len={len(final_response)})"
                )

                return {
                    "response": final_response,
                    "image": image_result["image"],
                    "image_seed": image_result["seed"],
                    "image_time": image_result["time"],
                    "image_prompt": image_prompt,
                    "time": total_time,
                    "tokens": tokens_used,
                }
            else:
                logger.error(f"Image generation failed: {image_result['error']}")
                # Return response with error note
                return {
                    "response": clean_response
                    + f"\n\n*(Image generation failed: {image_result['error']})*",
                    "time": elapsed,
                    "tokens": tokens_used,
                }

        # No image tool call, return normal response
        # Periodic cleanup for long conversations to prevent VRAM buildup
        if len(conversation_history) > 20:
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.debug("Periodic VRAM cleanup after long conversation")
            except ImportError:
                pass

        return {"response": assistant_message, "time": elapsed, "tokens": tokens_used}

    except Exception as e:
        error_str = str(e).lower()
        if "cuda" in error_str or "out of memory" in error_str:
            log_error(
                ErrorCode.VRAM_EXHAUSTED, "CUDA out of memory during text generation", e
            )
            return create_error_response(
                ErrorCode.VRAM_EXHAUSTED,
                "Out of GPU memory during generation. Try a shorter conversation or restart.",
            )
        elif "context" in error_str or "token" in error_str:
            log_error(ErrorCode.CONTEXT_TOO_LONG, "Context length exceeded", e)
            return create_error_response(
                ErrorCode.CONTEXT_TOO_LONG,
                "Conversation too long. Try starting a new session.",
            )
        else:
            log_error(ErrorCode.TEXT_GEN_FAILED, "Text generation failed", e)
            return create_error_response(ErrorCode.TEXT_GEN_FAILED, str(e))


# ============== API Routes ==============


@app.route("/")
def index():
    """Serve the chat interface"""
    return send_from_directory(".", "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages with session and memory support"""
    global chat_history

    data = request.json
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id")
    memory_text = data.get("memory_text", "")
    message_history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    logger.info("-" * 40)
    logger.info(f"NEW MESSAGE RECEIVED")
    if session_id:
        logger.info(f"Session: {session_id}")
    if memory_text:
        logger.info(f"Memory text: {len(memory_text)} chars")

    # Use provided history or fall back to server history
    history_to_use = message_history if message_history else chat_history

    # Generate response with memory text
    result = generate_response(user_message, history_to_use, memory_text)

    if "error" not in result:
        # Update server history
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": result["response"]})

        # Keep history manageable
        if len(chat_history) > 50:
            chat_history = chat_history[-40:]

        # Save to session if provided
        if session_id:
            if session_id not in sessions:
                sessions[session_id] = {
                    "id": session_id,
                    "created": datetime.now().isoformat(),
                    "messages": [],
                }
            sessions[session_id]["messages"].append(
                {"role": "user", "content": user_message}
            )
            sessions[session_id]["messages"].append(
                {"role": "assistant", "content": result["response"]}
            )
            sessions[session_id]["updated"] = datetime.now().isoformat()
            save_sessions()

    return jsonify(result)


@app.route("/api/clear", methods=["POST"])
def clear_history():
    """Clear conversation history"""
    global chat_history
    chat_history = []
    logger.info("Conversation history cleared")
    return jsonify({"status": "cleared"})


@app.route("/api/status", methods=["GET"])
def status():
    """Get server status"""
    model_name = os.path.basename(current_model_path) if current_model_path else "None"
    return jsonify(
        {
            "model_loaded": llm is not None,
            "model_path": current_model_path or "None",
            "model_name": model_name,
            "history_length": len(chat_history),
            "system_prompt_preview": SYSTEM_PROMPT[:200] + "...",
        }
    )


@app.route("/api/errors", methods=["GET"])
def get_error_codes():
    """Get reference of all error codes and their descriptions"""
    errors_by_category = {
        "System/Startup (E1XX)": {},
        "Model Loading (E2XX)": {},
        "Text Generation (E3XX)": {},
        "Image Generation (E4XX)": {},
        "API/Request (E5XX)": {},
        "File/Data (E6XX)": {},
        "Memory/Resource (E7XX)": {},
        "Shutdown (E8XX)": {},
        "Unknown (E9XX)": {},
    }

    for code in ErrorCode:
        code_str = f"E{code:03d}"
        category = None

        if 100 <= code < 200:
            category = "System/Startup (E1XX)"
        elif 200 <= code < 300:
            category = "Model Loading (E2XX)"
        elif 300 <= code < 400:
            category = "Text Generation (E3XX)"
        elif 400 <= code < 500:
            category = "Image Generation (E4XX)"
        elif 500 <= code < 600:
            category = "API/Request (E5XX)"
        elif 600 <= code < 700:
            category = "File/Data (E6XX)"
        elif 700 <= code < 800:
            category = "Memory/Resource (E7XX)"
        elif 800 <= code < 900:
            category = "Shutdown (E8XX)"
        elif 900 <= code < 1000:
            category = "Unknown (E9XX)"
        elif code == 0:
            continue  # Skip SUCCESS

        if category:
            errors_by_category[category][code_str] = {
                "name": code.name,
                "code_int": int(code),
                "description": ERROR_DESCRIPTIONS.get(code, "No description"),
            }

    return jsonify(
        {
            "error_codes": errors_by_category,
            "total_codes": len(ErrorCode) - 1,  # Exclude SUCCESS
            "format": "EXXX where X is a digit",
            "usage": 'Errors are returned as {"error": true, "code": "EXXX", "message": "...", "details": {...}}',
        }
    )


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration"""
    return jsonify(
        {
            "max_tokens": CONFIG["max_tokens"],
            "temperature": CONFIG["temperature"],
            "context_length": CONFIG["context_length"],
            "gpu_layers": CONFIG["gpu_layers"],
        }
    )


@app.route("/api/models", methods=["GET"])
def list_models():
    """List all available models"""
    models = scan_models()
    return jsonify(
        {
            "models": models,
            "current_model": current_model_path,
            "models_dir": CONFIG["models_dir"],
        }
    )


@app.route("/api/models/load", methods=["POST"])
def load_model_api():
    """Load a specific model"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        model_path = data.get("model_path", "").strip()

        if not model_path:
            return jsonify({"error": "No model path provided"}), 400

        # Normalize the path
        model_path = os.path.normpath(model_path)

        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return jsonify({"error": f"Model not found: {model_path}"}), 404

        logger.info(f"API request to load model: {model_path}")
        logger.info(
            f"Model file size: {os.path.getsize(model_path) / (1024**3):.2f} GB"
        )

        success = load_model(model_path)

        if success:
            return jsonify(
                {
                    "status": "loaded",
                    "model_path": current_model_path,
                    "model_name": os.path.basename(current_model_path),
                }
            )
        else:
            return jsonify(
                {"error": "Failed to load model. Check server console for details."}
            ), 500

    except Exception as e:
        logger.error(f"Exception in load_model_api: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/api/system-prompt", methods=["GET", "POST"])
def system_prompt_api():
    """Get or update system prompt"""
    global SYSTEM_PROMPT

    if request.method == "GET":
        return jsonify(
            {"system_prompt": SYSTEM_PROMPT, "file_path": SYSTEM_PROMPT_FILE}
        )

    data = request.json
    new_prompt = data.get("system_prompt", "").strip()

    if new_prompt:
        SYSTEM_PROMPT = new_prompt
        # Save to file for persistence
        save_system_prompt(new_prompt)
        logger.info("System prompt updated and saved to file")
        return jsonify({"status": "updated", "system_prompt": SYSTEM_PROMPT})

    return jsonify({"error": "Empty prompt"}), 400


@app.route("/api/system-prompt/reload", methods=["POST"])
def reload_system_prompt():
    """Reload system prompt from file"""
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = load_system_prompt()
    return jsonify({"status": "reloaded", "system_prompt": SYSTEM_PROMPT})


# ============== Memory API ==============


@app.route("/api/memories", methods=["GET"])
def get_memories():
    """Get all stored memories"""
    return jsonify({"memories": memories})


@app.route("/api/memories", methods=["POST"])
def update_memories():
    """Update memories (replace all)"""
    global memories
    data = request.json
    new_memories = data.get("memories", {})

    memories = new_memories
    save_memories()

    logger.info(f"Memories updated: {len(memories)} items")
    return jsonify({"status": "updated", "memories": memories})


# ============== Image Generation API ==============


@app.route("/api/image/models", methods=["GET"])
def get_image_models():
    """Get available image generation models (dynamically scanned)"""
    available_models = scan_image_models()
    models = []
    for model_id, info in available_models.items():
        models.append(
            {
                "id": model_id,
                "name": info["name"],
                "type": info["type"],
                "path": info["path"],
                "uncensored": info.get("uncensored", True),
            }
        )
    return jsonify(
        {
            "models": models,
            "current_model": current_image_model,
            "models_dir": IMAGE_MODELS_DIR,
        }
    )


@app.route("/api/image/load", methods=["POST"])
def load_image_model_api():
    """Load an image generation model"""
    data = request.json
    model_id = data.get("model_id", "")

    if not model_id:
        return jsonify({"error": "No model_id provided"}), 400

    result = load_image_model(model_id)

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/image/generate", methods=["POST"])
def generate_image_api():
    """Generate an image from a prompt"""
    data = request.json
    prompt = data.get("prompt", "").strip()
    negative_prompt = data.get("negative_prompt", "")
    width = data.get("width", 512)
    height = data.get("height", 512)
    steps = data.get("steps", 25)
    cfg_scale = data.get("cfg_scale", 7.0)
    seed = data.get("seed", -1)

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    # Validate dimensions
    width = min(max(width, 256), 1024)
    height = min(max(height, 256), 1024)
    steps = min(max(steps, 10), 50)

    result = generate_image(
        prompt, negative_prompt, width, height, steps, cfg_scale, seed
    )

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/image/status", methods=["GET"])
def image_status():
    """Get current image generation status"""
    available_models = scan_image_models()
    return jsonify(
        {
            "model_loaded": image_pipe is not None,
            "current_model": current_image_model,
            "available_models": list(available_models.keys()),
            "models_dir": IMAGE_MODELS_DIR,
            "cuda_available": CUDA_AVAILABLE,
            "cuda_device": CUDA_DEVICE_NAME,
        }
    )


@app.route("/api/cuda", methods=["GET"])
def cuda_status():
    """Get CUDA/GPU status"""
    return jsonify(
        {
            "cuda_available": CUDA_AVAILABLE,
            "device_name": CUDA_DEVICE_NAME,
            "message": "GPU acceleration active"
            if CUDA_AVAILABLE
            else "GPU not available - run 'python install_llama.py' to fix",
        }
    )


@app.route("/api/vram", methods=["GET"])
def vram_status():
    """Get detailed VRAM usage statistics"""
    try:
        import torch

        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            free = total - reserved

            return jsonify(
                {
                    "cuda_available": True,
                    "device_name": CUDA_DEVICE_NAME,
                    "allocated_gb": round(allocated, 2),
                    "reserved_gb": round(reserved, 2),
                    "free_gb": round(free, 2),
                    "total_gb": round(total, 2),
                    "usage_percent": round((reserved / total) * 100, 1),
                    "text_model_loaded": llm is not None,
                    "image_model_loaded": image_pipe is not None,
                }
            )
        else:
            return jsonify({"cuda_available": False, "message": "CUDA not available"})
    except ImportError:
        return jsonify({"cuda_available": False, "message": "PyTorch not installed"})


@app.route("/api/shutdown", methods=["POST"])
def shutdown_server():
    """Gracefully shutdown the server and free all resources

    This endpoint:
    1. Saves all pending data
    2. Unloads all models
    3. Clears CUDA cache
    4. Shuts down the Flask server

    Use with caution - this will terminate the server process.
    """
    # Check for optional confirmation parameter
    data = request.json or {}
    if not data.get("confirm", False):
        return jsonify(
            {
                "error": "Shutdown requires confirmation",
                "message": 'Send POST with {"confirm": true} to shutdown',
            }
        ), 400

    logger.info("Shutdown requested via API")

    # Run cleanup in a separate thread to allow response to be sent
    def delayed_shutdown():
        time.sleep(0.5)  # Allow response to be sent
        cleanup_resources()
        os._exit(0)  # Force exit after cleanup

    shutdown_thread = threading.Thread(target=delayed_shutdown)
    shutdown_thread.daemon = True
    shutdown_thread.start()

    return jsonify(
        {"status": "shutting_down", "message": "Server is shutting down gracefully"}
    )


@app.route("/api/unload", methods=["POST"])
def unload_models():
    """Unload models without shutting down the server

    Useful for freeing VRAM without stopping the server.
    """
    global \
        llm, \
        current_model_path, \
        image_pipe, \
        current_image_model, \
        current_image_model_type

    data = request.json or {}
    unload_text = data.get("text_model", False)
    unload_image = data.get("image_model", False)
    unload_all = data.get("all", False)

    results = []

    if unload_all or unload_text:
        if llm is not None:
            try:
                del llm
                llm = None
                current_model_path = None
                gc.collect()
                results.append("Text model unloaded")
            except Exception as e:
                results.append(f"Error unloading text model: {e}")
        else:
            results.append("No text model loaded")

    if unload_all or unload_image:
        if image_pipe is not None:
            try:
                del image_pipe
                image_pipe = None
                current_image_model = None
                current_image_model_type = None
                gc.collect()
                results.append("Image model unloaded")
            except Exception as e:
                results.append(f"Error unloading image model: {e}")
        else:
            results.append("No image model loaded")

    # Clear CUDA cache after unloading
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            results.append("CUDA cache cleared")
    except ImportError:
        pass

    if not results:
        return jsonify(
            {"error": "Specify text_model, image_model, or all to unload"}
        ), 400

    log_vram_usage("after_unload")

    return jsonify(
        {
            "status": "success",
            "results": results,
            "text_model_loaded": llm is not None,
            "image_model_loaded": image_pipe is not None,
        }
    )


@app.route("/api/memories/<key>", methods=["PUT"])
def save_memory(key):
    """Save a single memory"""
    global memories
    data = request.json
    value = data.get("value", "")

    memories[key] = value
    save_memories()

    logger.info(f"Memory saved: {key}")
    return jsonify({"status": "saved", "key": key, "value": value})


@app.route("/api/memories/<key>", methods=["DELETE"])
def delete_memory(key):
    """Delete a single memory"""
    global memories

    if key in memories:
        del memories[key]
        save_memories()
        logger.info(f"Memory deleted: {key}")
        return jsonify({"status": "deleted", "key": key})

    return jsonify({"error": "Memory not found"}), 404


# ============== Session API ==============


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Get all sessions"""
    session_list = list(sessions.values())
    # Sort by updated time, most recent first
    session_list.sort(
        key=lambda x: x.get("updated", x.get("created", "")), reverse=True
    )
    return jsonify({"sessions": session_list})


@app.route("/api/sessions", methods=["POST"])
def create_session():
    """Create a new session"""
    data = request.json
    session_id = data.get("id") or str(uuid.uuid4())
    name = data.get("name", f"Session {len(sessions) + 1}")

    sessions[session_id] = {
        "id": session_id,
        "name": name,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "messages": [],
    }
    save_sessions()

    logger.info(f"Session created: {session_id}")
    return jsonify({"status": "created", "session": sessions[session_id]})


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """Get a specific session"""
    if session_id in sessions:
        return jsonify({"session": sessions[session_id]})
    return jsonify({"error": "Session not found"}), 404


@app.route("/api/sessions/<session_id>", methods=["PUT"])
def update_session(session_id):
    """Update a session"""
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    data = request.json

    if "name" in data:
        sessions[session_id]["name"] = data["name"]
    if "messages" in data:
        sessions[session_id]["messages"] = data["messages"]

    sessions[session_id]["updated"] = datetime.now().isoformat()
    save_sessions()

    logger.info(f"Session updated: {session_id}")
    return jsonify({"status": "updated", "session": sessions[session_id]})


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a session"""
    if session_id in sessions:
        del sessions[session_id]
        save_sessions()
        logger.info(f"Session deleted: {session_id}")
        return jsonify({"status": "deleted", "session_id": session_id})

    return jsonify({"error": "Session not found"}), 404


# ============== Main ==============


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Unity AI Lab - Local Chat Server")
    parser.add_argument(
        "--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host to bind to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8080)),
        help="Port to listen on",
    )
    parser.add_argument("--models-dir", default="./models", help="Models directory")
    args = parser.parse_args()

    # Update config from args
    CONFIG["host"] = args.host
    CONFIG["port"] = args.port
    CONFIG["models_dir"] = args.models_dir

    logger.info("=" * 60)
    logger.info("UNITY AI LAB - LOCAL CHAT SERVER")
    logger.info("www.unityailab.com")
    logger.info("=" * 60)

    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()

    # Check CUDA status FIRST
    check_cuda_status()

    logger.info("=" * 60)
    logger.info("Configuration:")
    for key, value in CONFIG.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    # Create directories
    os.makedirs(CONFIG["models_dir"], exist_ok=True)
    os.makedirs(os.path.join(CONFIG["models_dir"], "image"), exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load saved data
    load_data_files()

    # Scan available models (no auto-loading - user selects from UI)
    available_models = scan_models()
    image_models = scan_image_models()

    logger.info(
        f"Found {len(available_models)} text models, {len(image_models)} image models"
    )

    if available_models:
        logger.info("Text models ready - select one from the UI")
    else:
        logger.info("No text models found - place .gguf files in models/ folder")

    if image_models:
        logger.info("Image models ready - select one from the UI")
    else:
        logger.info("No image models found - place models in models/image/ folder")

    logger.info("=" * 60)
    logger.info(f"Server running at http://{CONFIG['host']}:{CONFIG['port']}")
    logger.info("Open this URL in your browser")
    logger.info("Press Ctrl+C to shutdown gracefully")
    logger.info("=" * 60)

    try:
        app.run(host=CONFIG["host"], port=CONFIG["port"], debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        # Ensure cleanup happens even if Flask exits unexpectedly
        cleanup_resources()


if __name__ == "__main__":
    main()

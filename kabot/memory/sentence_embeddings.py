"""Sentence-Transformers embedding provider with subprocess isolation.

The embedding model runs in a **child process** (`subprocess.Popen`) so that
when it's terminated, the OS reclaims ALL memory immediately — solving CPython's
arena-allocator retention issue where ~350 MB stays resident after `del`.

Architecture:
  Main process (91 MB) ──JSON line──▶ Worker process (loads model, +359 MB)
                        ◀──JSON line──  │
                                        └─ process.kill() → OS reclaims all 359 MB → main stays at 91 MB
"""

import hashlib
import json
import os
import subprocess
import sys
import threading
import time

from loguru import logger


class SentenceEmbeddingProvider:
    """Local embedding provider using Sentence-Transformers in a subprocess.

    The model runs in a child process started via `subprocess.Popen`. When
    auto-unload fires, the child is killed and ALL its memory is returned to
    the OS — unlike in-process unloading where CPython retains ~350 MB.

    Supports models like:
    - all-MiniLM-L6-v2 (recommended, 384 dimensions, fast)
    - all-mpnet-base-v2 (768 dimensions, more accurate)
    - paraphrase-multilingual-MiniLM-L12-v2 (multilingual support)
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2", auto_unload_seconds: int = 300):
        if auto_unload_seconds < 0:
            raise ValueError("auto_unload_seconds must be >= 0")
        self.model_name = model
        self._auto_unload_seconds = auto_unload_seconds
        self._auto_unload_enabled = auto_unload_seconds > 0

        # Subprocess handle
        self._process: subprocess.Popen | None = None

        # Embedding cache (lives in main process, lightweight)
        self._cache: dict[str, list[float]] = {}
        self._cache_size = 1000

        # Timing and thread safety
        self._last_used: float | None = None
        self._unload_timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._req_counter = 0

    def _is_subprocess_alive(self) -> bool:
        """Check if the embedding subprocess is running."""
        return self._process is not None and self._process.poll() is None

    def _start_subprocess(self):
        """Start the embedding worker process if not already running."""
        if self._is_subprocess_alive():
            return

        with self._lock:
            if self._is_subprocess_alive():
                return

            worker_module = "kabot.memory._embedding_worker"
            logger.info(f"Starting embedding subprocess: python -u -m {worker_module} {self.model_name}")

            # CRITICAL: -u flag forces unbuffered stdout on Windows.
            # Without it, stdout is fully buffered for piped processes,
            # causing readline() in the parent to hang indefinitely.
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            self._process = subprocess.Popen(
                [sys.executable, "-u", "-m", worker_module, self.model_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # CRITICAL: stderr must NOT be PIPE — sentence-transformers writes
                # progress bars + warnings during model load. If the pipe buffer fills
                # (64KB on Windows), the subprocess blocks and never sends init to stdout.
                # Using None (inherit) instead of DEVNULL to allow stderr output for debugging
                stderr=None,
                text=True,
                bufsize=1,
                env=env,
            )

            # Wait for "init" ready signal (model loading takes time)
            try:
                ready_line = self._process.stdout.readline()
                if not ready_line:
                    raise RuntimeError("Subprocess exited without ready signal (model load may have failed)")

                ready = json.loads(ready_line)
                if ready.get("status") != "ok":
                    raise RuntimeError(f"Subprocess init failed: {ready}")

                logger.info(f"Embedding subprocess ready (PID={self._process.pid})")

            except Exception as e:
                logger.error(f"Embedding subprocess startup failed: {e}")
                self._kill_subprocess()
                raise

    def _kill_subprocess(self):
        """Terminate the subprocess — OS reclaims ALL its memory."""
        if self._process is not None:
            pid = self._process.pid
            try:
                # Try graceful shutdown first
                if self._process.poll() is None:
                    try:
                        self._process.stdin.write(json.dumps({"id": "shutdown", "type": "shutdown"}) + "\n")
                        self._process.stdin.flush()
                        self._process.wait(timeout=3)
                    except Exception:
                        pass

                # Force kill if still alive
                if self._process.poll() is None:
                    self._process.kill()
                    self._process.wait(timeout=3)

            except Exception as e:
                logger.warning(f"Error killing embedding subprocess: {e}")
            finally:
                # Close pipes (stderr is DEVNULL, no pipe to close)
                for pipe in (self._process.stdin, self._process.stdout):
                    try:
                        if pipe:
                            pipe.close()
                    except Exception:
                        pass
                self._process = None
                logger.info(f"Embedding subprocess terminated (PID={pid}) — memory returned to OS")

    def _send_request(self, req_type: str, data) -> any:
        """Send a request to the subprocess and wait for JSON response."""
        self._start_subprocess()
        self._req_counter += 1
        req_id = f"req_{self._req_counter}"

        request = json.dumps({"id": req_id, "type": req_type, "data": data})

        try:
            self._process.stdin.write(request + "\n")
            self._process.stdin.flush()

            response_line = self._process.stdout.readline()
            if not response_line:
                raise RuntimeError("Subprocess closed stdout unexpectedly")

            response = json.loads(response_line)
            if response.get("status") == "error":
                raise RuntimeError(f"Embedding error: {response.get('result')}")

            return response.get("result")

        except (BrokenPipeError, OSError) as e:
            logger.error(f"Subprocess pipe broken: {e}")
            self._kill_subprocess()
            raise RuntimeError("Embedding subprocess crashed") from e

    async def warmup(self):
        """Pre-load the embedding model subprocess in background (non-blocking)."""
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._start_subprocess)

    async def embed(self, text: str) -> list[float] | None:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        try:
            # Check cache (cache is in main process — zero overhead)
            cache_key = hashlib.md5(text.encode()).hexdigest()
            if cache_key in self._cache:
                if self._auto_unload_enabled:
                    self._reset_unload_timer()
                return self._cache[cache_key]

            self._last_used = time.time()

            # Run blocking subprocess I/O in thread executor
            # Note: no lock here — subprocess pipe is inherently serialized
            import asyncio
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, self._send_request, "embed", text
            )

            if embedding:
                if len(self._cache) >= self._cache_size:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = embedding

            if self._auto_unload_enabled:
                self._reset_unload_timer()

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings
        """
        try:
            self._last_used = time.time()

            import asyncio
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self._send_request, "embed_batch", texts
            )

            # Cache results
            results = []
            for text, embedding in zip(texts, embeddings):
                cache_key = hashlib.md5(text.encode()).hexdigest()
                if len(self._cache) >= self._cache_size:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = embedding
                results.append(embedding)

            if self._auto_unload_enabled:
                self._reset_unload_timer()

            return results

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)

    def _reset_unload_timer(self):
        """Reset the auto-unload timer."""
        if self._unload_timer:
            self._unload_timer.cancel()

        self._unload_timer = threading.Timer(
            self._auto_unload_seconds,
            self._auto_unload_callback,
        )
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _auto_unload_callback(self):
        """Timer callback — kill subprocess after idle timeout."""
        with self._lock:
            if self._is_subprocess_alive() and self._last_used is not None:
                idle_time = time.time() - self._last_used
                if idle_time >= self._auto_unload_seconds:
                    logger.info(f"Auto-unloading embedding subprocess after {idle_time:.0f}s idle")
                    self._kill_subprocess()

    def unload_model(self):
        """Manually terminate the subprocess to free ALL RAM."""
        with self._lock:
            if self._unload_timer:
                self._unload_timer.cancel()
                self._unload_timer = None
            self._kill_subprocess()
            self._cache.clear()

    # Backward-compatible aliases
    def _unload_model_internal(self):
        """Internal unload — kills subprocess."""
        self._kill_subprocess()

    def _load_model(self):
        """Start subprocess (backward-compatible name)."""
        self._start_subprocess()

    def get_memory_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "model_loaded": self._is_subprocess_alive(),
            "subprocess_pid": self._process.pid if self._process and self._process.poll() is None else None,
            "last_used": self._last_used,
            "auto_unload_seconds": self._auto_unload_seconds,
            "auto_unload_enabled": self._auto_unload_enabled,
            "cache_size": len(self._cache),
        }

    def __del__(self):
        """Cleanup on destruction."""
        try:
            if self._unload_timer:
                self._unload_timer.cancel()
            self._kill_subprocess()
        except Exception:
            pass

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        dimensions_map = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "paraphrase-multilingual-MiniLM-L12-v2": 384,
            "all-distilroberta-v1": 768,
            "all-MiniLM-L12-v2": 384,
        }
        return dimensions_map.get(self.model_name, 384)

    def check_connection(self) -> bool:
        """Check if model can be loaded."""
        try:
            self._start_subprocess()
            return self._is_subprocess_alive()
        except Exception:
            return False

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "cached_items": len(self._cache),
            "loaded": self._is_subprocess_alive(),
            "subprocess_pid": self._process.pid if self._process and self._process.poll() is None else None,
        }

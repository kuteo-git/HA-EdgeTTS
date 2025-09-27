"""EdgeTTS Server Manager."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import DEFAULT_HOST, DEFAULT_PORT, SERVER_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class EdgeTTSServerManager:
    """Manage EdgeTTS server lifecycle."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize server manager."""
        self.hass = hass
        self.process: subprocess.Popen | None = None
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT
        self._server_ready = False

    async def start_server(self) -> bool:
        """Start EdgeTTS server."""
        if self.process and self.process.poll() is None:
            _LOGGER.warning("Server already running")
            return True

        try:
            # Install requirements first
            await self._install_requirements()
            
            # Start server process
            server_script = Path(__file__).parent / "edgetts_server.py"
            
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).parent)
            
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(server_script),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            _LOGGER.info(f"Started EdgeTTS server with PID: {self.process.pid}")
            
            # Wait for server to be ready
            await self._wait_for_server_ready()
            
            return True
            
        except Exception as err:
            _LOGGER.error(f"Failed to start EdgeTTS server: {err}")
            return False

    async def stop_server(self) -> None:
        """Stop EdgeTTS server."""
        if self.process:
            try:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
                _LOGGER.info("EdgeTTS server stopped")
            except Exception as err:
                _LOGGER.error(f"Error stopping server: {err}")
            finally:
                self.process = None
                self._server_ready = False

    async def _install_requirements(self) -> None:
        """Install required packages."""
        requirements = [
            "edge-tts==6.1.12",
            "pydub==0.25.1", 
            "flask==3.0.0",
            "requests==2.31.0"
        ]
        
        for requirement in requirements:
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", requirement,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.wait()
            except Exception as err:
                _LOGGER.warning(f"Failed to install {requirement}: {err}")

    async def _wait_for_server_ready(self) -> None:
        """Wait for server to be ready."""
        import aiohttp
        
        url = f"http://{self.host}:{self.port}/health"
        timeout = aiohttp.ClientTimeout(total=2)
        
        for _ in range(15):  # Try for 30 seconds
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            self._server_ready = True
                            _LOGGER.info("EdgeTTS server is ready")
                            return
            except Exception:
                pass
            
            await asyncio.sleep(2)
        
        raise Exception("EdgeTTS server failed to start within timeout")

    @property
    def is_ready(self) -> bool:
        """Check if server is ready."""
        return self._server_ready and self.process and self.process.poll() is None

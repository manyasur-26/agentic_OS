"""
Main entry point for Agentic OS daemon.

This is the primary process that the systemd service runs.
It initializes all core components and keeps them running.
"""

import asyncio
import signal
import sys
from pathlib import Path

from .config import get_config
from .logging_setup import setup_logging, get_logger
from .intent_bus import get_intent_bus


class AgenticOSDaemon:
    """
    Main daemon class for Agentic OS.
    
    Manages lifecycle of all core components:
    - Intent Bus
    - Planner
    - Memory
    - Scheduler
    - Tool Router
    """
    
    def __init__(self):
        """Initialize the daemon."""
        self.config = get_config()
        self.logger = get_logger("daemon")
        self.intent_bus = get_intent_bus()
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """
        Initialize all core components.
        
        This will be expanded in later phases to include:
        - Planner initialization
        - Memory initialization
        - Scheduler initialization
        - Tool router initialization
        """
        self.logger.info("Initializing Agentic OS daemon")
        
        # Start intent bus
        await self.intent_bus.start()
        self.logger.info("Intent bus started")
        
        # TODO: Initialize other components in future phases
        # - self.planner = Planner(...)
        # - self.memory = Memory(...)
        # - self.scheduler = Scheduler(...)
        # - self.tool_router = ToolRouter(...)
        
        self.logger.info("All components initialized")
    
    async def run(self) -> None:
        """
        Main run loop for the daemon.
        
        Keeps the daemon alive until shutdown is requested.
        """
        self._running = True
        self.logger.info("Agentic OS daemon running")
        
        try:
            # Wait for shutdown signal
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Daemon cancelled")
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """
        Gracefully shutdown all components.
        """
        self.logger.info("Shutting down Agentic OS daemon")
        self._running = False
        
        # Stop intent bus
        await self.intent_bus.stop()
        
        # TODO: Shutdown other components in future phases
        
        self.logger.info("Agentic OS daemon stopped")
    
    def signal_handler(self, signum, frame) -> None:
        """
        Handle shutdown signals (SIGTERM, SIGINT).
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info("Received signal %d, initiating shutdown", signum)
        self._shutdown_event.set()


async def main() -> int:
    """
    Main async entry point.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Setup logging
        setup_logging()
        logger = get_logger("main")
        logger.info("Starting Agentic OS daemon")
        
        # Create and initialize daemon
        daemon = AgenticOSDaemon()
        await daemon.initialize()
        
        # Setup signal handlers
        import signal
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: daemon.signal_handler(sig, None)
            )
        
        # Run daemon
        await daemon.run()
        
        logger.info("Agentic OS daemon exited cleanly")
        return 0
        
    except Exception as e:
        logger = get_logger("main")
        logger.error("Fatal error in daemon", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

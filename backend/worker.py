#!/usr/bin/env python3
"""
Background Worker for Processing Message Queue
Consumes booking confirmation messages from Redis Streams
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import redis.asyncio as redis
from app.core.config import settings
from app.core.queue import MessageQueue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Worker:
    """Background worker process"""
    
    def __init__(self):
        self.running = False
        self.redis_client = None
        self.queue = None
    
    async def start(self):
        """Start the worker"""
        self.running = True
        
        # Connect to Redis
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        
        self.queue = MessageQueue(self.redis_client)
        
        logger.info("Worker started successfully")
        logger.info(f"Listening for messages on: {self.queue.CONFIRMATION_STREAM}")
        
        try:
            # Process confirmations (blocking loop)
            await self.queue.process_confirmations(consumer_name="worker-1")
        except asyncio.CancelledError:
            logger.info("Worker cancelled, shutting down...")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Worker shutdown complete")


async def main():
    """Main entry point"""
    worker = Worker()
    
    # Handle signals for graceful shutdown
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        loop.create_task(worker.shutdown())
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    # Start worker
    await worker.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        sys.exit(1)

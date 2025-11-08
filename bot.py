import asyncio
import signal
import sys
from monitor_service import MonitorService
from logger import setup_logger


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n")
    logger.info("Received interrupt signal (Ctrl+C)")
    sys.exit(0)


if __name__ == "__main__":
    logger = setup_logger()

    # Signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform != 'win32':
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        monitor = MonitorService()
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

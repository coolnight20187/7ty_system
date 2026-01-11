#!/usr/bin/env python
"""
Quick start script to run the FastAPI server with basic initialization
"""
import sys
import logging
from pathlib import Path

# Add the project directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    import uvicorn
    
    # Configure and run server
    config = uvicorn.Config(
        app="main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
        workers=1
    )
    
    server = uvicorn.Server(config)
    
    logger.info("Starting 7TY.VN System...")
    logger.info("Server will be available at http://localhost:8000")
    logger.info("API Documentation at http://localhost:8000/docs")
    
    try:
        import asyncio
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

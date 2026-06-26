import sys
import asyncio
import logging

logger = logging.getLogger(__name__)

async def execute_main_script(action: str):
    """Runs main.py as a separate OS process and captures all logs."""
    logger.info("🚀 Launching subprocess for: %s", action)
    
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "interfaces.cli.main", "--action", action,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    out_str = stdout.decode().strip()
    err_str = stderr.decode().strip()
    
    if out_str:
        logger.info("[MAIN.PY OUTPUT]\n%s", out_str)
    
    if process.returncode != 0:
        logger.error("[MAIN.PY ERROR/CRASH returncode=%s]\n%s", process.returncode, err_str)
    elif err_str:
        logger.info("[MAIN.PY STDERR]\n%s", err_str)
    else:
        logger.info("Subprocess for %s completed successfully.", action)
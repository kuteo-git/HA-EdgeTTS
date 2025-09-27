import subprocess
import sys
import os
import time
import glob
import asyncio

__BASE_PATH = '/config/pyscript/servers'
__INSTALL_REQUIREMENTS_FILE = 'requirements.txt'
__TTS_SERVER_PATH = f'{__BASE_PATH}/edgetts'
__TTS_SERVER_FILE = 'edgetts_server.py'

def __install_requirements(
    requirements_file:str, 
    upgrade=False, 
    user=False
):
    try:
        # Check if requirements file exists
        if not os.path.exists(requirements_file):
            log.error(f"Error: {requirements_file} not found!")
            return False
        
        # Build the pip command
        cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
        
        # Add optional flags
        if upgrade:
            cmd.append("--upgrade")
        if user:
            cmd.append("--user")
        
        log.info(f"Running: {' '.join(cmd)}")
        
        # Execute the command
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        log.info("Installation completed successfully!")
        log.info(result.stdout)
        return True
        
    except subprocess.CalledProcessError as e:
        log.error(f"Error during installation: {e}")
        log.error(f"Return code: {e.returncode}")
        log.error(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return False


def __start_server(
    path:str,
    file:str
):  
    try:
        # Kill any existing instances
        subprocess.run(['pkill', '-f', file], check=False)
        await asyncio.sleep(3)
        
        # Start new instance
        subprocess.Popen([
            'python3', 
            f'{path}/{file}'
        ], cwd='/config/pyscript')
        
        log.info(f"`{file}` server started via Pyscript")
        
    except Exception as e:
        log.error(f"Failed to start {file} server: {e}")


@time_trigger("startup")
def start_edgetts_server_on_boot():
    # Install requirements
    __install_requirements(
        requirements_file = f"{__TTS_SERVER_PATH}/{__INSTALL_REQUIREMENTS_FILE}"
    )

    # Start servers
    __start_server(
        path = __TTS_SERVER_PATH,
        file = __TTS_SERVER_FILE
    )
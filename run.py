import subprocess
subprocess.run(["sudo", "apt-get", "upgrade"])
subprocess.run(["sudo", "apt-get", "update"])
subprocess.run(["sudo", "apt", "install", "libsm6"])
subprocess.run(["sudo", "apt", "install", "libxext6"])
subprocess.run(["sudo", "apt", "install", "ffmpeg"])
subprocess.run(["sudo", "apt", "install", "libfontconfig1"])
subprocess.run(["sudo", "apt", "install", "libxrender1"])
subprocess.run(["sudo", "apt", "install", "libgl1-mesa-glx"])
subprocess.run(["uvicorn", "server:app"])


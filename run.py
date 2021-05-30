import subprocess
# subprocess.run(["apt-get", "upgrade"])
# subprocess.run(["apt-get", "update"])
# subprocess.run(["apt", "install", "libsm6"])
# subprocess.run(["apt", "install", "libxext6"])
# subprocess.run(["apt", "install", "ffmpeg"])
# subprocess.run(["apt", "install", "libfontconfig1"])
# subprocess.run(["apt", "install", "libxrender1"])
# subprocess.run(["apt", "install", "libgl1-mesa-glx"])
subprocess.run(["uvicorn", "server:app"])


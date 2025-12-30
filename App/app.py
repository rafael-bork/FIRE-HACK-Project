import subprocess
import os
import sys

DEPLOYMENT_DIR = "Notebooks/5Deployment/"

os.chdir(DEPLOYMENT_DIR)
subprocess.run([sys.executable, "app.py"])
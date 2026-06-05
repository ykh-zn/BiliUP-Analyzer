import subprocess
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, os.path.join(project_root, 'crawler', 'bilibili_selenium.py')] + sys.argv[1:], cwd=project_root)

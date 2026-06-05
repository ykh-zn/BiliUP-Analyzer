import subprocess
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, '-m', 'streamlit', 'run', os.path.join(project_root, 'dashboard', 'app.py')], cwd=project_root)

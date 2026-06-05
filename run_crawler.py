import subprocess
import sys
subprocess.run([sys.executable, 'crawler/bilibili_selenium.py'] + sys.argv[1:])

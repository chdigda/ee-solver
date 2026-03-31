import subprocess
import webbrowser
import time

if __name__ == "__main__":
    proc = subprocess.Popen(
        ["uvicorn", "server:app", "--port", "8100", "--reload"],
    )
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8100")
    proc.wait()

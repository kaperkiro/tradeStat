import sys
import threading
import time


def thinking_spinner(message: str, stop_event: threading.Event):
    dots = ["", ".", "..", "..."]
    max_len = len(message) + len("...")

    i = 0
    while not stop_event.is_set():
        text = f"{message}{dots[i % len(dots)]}"
        sys.stdout.write("\r" + text.ljust(max_len))
        sys.stdout.flush()
        time.sleep(0.4)
        i += 1

    # Clear line on exit
    sys.stdout.write("\r" + " " * max_len + "\r")
    sys.stdout.flush()


def start_spinner_sim():
    # --- loading setup ---
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=thinking_spinner,
        args=("Running Simulation", stop_event),
        daemon=True,
    )
    spinner_thread.start()
    return stop_event, spinner_thread


def start_spinnerAI():
    # --- loading setup ---
    stop_event = threading.Event()
    spinner_thread = threading.Thread(
        target=thinking_spinner,
        args=("Generating Strategy", stop_event),
        daemon=True,
    )
    spinner_thread.start()
    return stop_event, spinner_thread


def stop_spinner(stop_event, spinner_thread):
    stop_event.set()
    spinner_thread.join()

# Fixture: R5 — threading.Thread() inside a function
import threading


def handle_request(data):
    t = threading.Thread(target=process, args=(data,))
    t.start()


def process(data):
    pass

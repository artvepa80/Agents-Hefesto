# Fixture: R3 — Session() without context-manager or .close()
import requests


def fetch_data(url):
    session = requests.Session()
    response = session.get(url)
    return response.json()
    # session is never closed!

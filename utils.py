"""
utils.py

Helpers: resilient requests session and a retry decorator with exponential backoff.
"""
import time
import logging
from typing import Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_requests_session(retries: int = 3, backoff_factor: float = 0.5, status_forcelist=(500, 502, 503, 504)) -> requests.Session:
    sess = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount('http://', adapter)
    sess.mount('https://', adapter)
    sess.headers.update({'User-Agent': 'epermits-scraper/1.0'})
    return sess


def retry_backoff(max_attempts: int = 4, initial_delay: float = 0.5, factor: float = 2.0, exceptions=(Exception,)) -> Callable:
    def decorator(fn: Callable):
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = initial_delay
            while True:
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logging.exception('Max retry attempts reached for %s', fn.__name__)
                        raise
                    logging.warning('Error in %s: %s. Retrying in %.1fs (attempt %d/%d)', fn.__name__, e, delay, attempt, max_attempts)
                    time.sleep(delay)
                    delay *= factor
        return wrapper
    return decorator

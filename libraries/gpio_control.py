import RPi.GPIO as GPIO
import time
from libraries.logger import get_logger
import threading

logger = get_logger("GPIO")

class GPIOController:
    def __init__(self):
        # Use a lock to protect the underlying RPi.GPIO calls.  Although
        # the library is mostly thread‑safe, concurrent pulses on different
        # pins can interfere with each other; serializing the calls makes
        # behaviour predictable when multiple stepper threads invoke the
        # controller at once.
        self._lock = threading.Lock()
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            logger.info("GPIO controller initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            raise

    def setup_output(self, pin):
        with self._lock:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        logger.debug(f"Pin {pin} set as output")

    def setup_input(self, pin, pull_up_down=GPIO.PUD_UP):
        with self._lock:
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull_up_down)
        logger.debug(f"Pin {pin} set as input")

    def write_pin(self, pin, state):
        with self._lock:
            GPIO.output(pin, state)
        
    def read_pin(self, pin):
        with self._lock:
            return GPIO.input(pin)

    def pulse(self, pin, delay=0.001):
        # note: keep the sleep outside of lock so we don't hold it while
        # waiting; only guard the discrete writes so two motors don't try to
        # flip the same pin simultaneously.
        with self._lock:
            GPIO.output(pin, GPIO.HIGH)
        time.sleep(delay)
        with self._lock:
            GPIO.output(pin, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
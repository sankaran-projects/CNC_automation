import RPi.GPIO as GPIO
import time
import pigpio
from libraries.logger import get_logger

logger = get_logger("GPIO")

class GPIOController:
    def __init__(self, use_pigpio: bool = True):
        """Initialize the GPIO controller.

        By default we try to use pigpio for hardware-timed pulses. The
        pigpio instance is stored on ``self.pi`` so that other components
        (e.g. :class:`StepperMotor`) can access it.  If pigpio is not
        available the class falls back to the legacy RPi.GPIO interface.
        """
        # allow the caller to disable pigpio in tests or on unsupported
        # hardware
        self.use_pigpio = use_pigpio

        try:
            if self.use_pigpio:
                # create a pigpio connection and keep it around
                self.pi = pigpio.pi()
            
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            logger.info("GPIO controller initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            # propagate so the application can fail fast
            raise

    def setup_output(self, pin):
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        logger.debug(f"Pin {pin} set as output")

    def setup_input(self, pin, pull_up_down=GPIO.PUD_UP):
        GPIO.setup(pin, GPIO.IN, pull_up_down=pull_up_down)
        logger.debug(f"Pin {pin} set as input")

    def write_pin(self, pin, state):
        GPIO.output(pin, state)
        
    def read_pin(self, pin):
        return GPIO.input(pin)

    def pulse(self, pin, delay=0.001):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(pin, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
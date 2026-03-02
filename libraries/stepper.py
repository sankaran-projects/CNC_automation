import time
import threading
import pigpio
import RPi.GPIO as GPIO
from libraries.logger import get_logger
from concurrent.futures import ThreadPoolExecutor


executor = ThreadPoolExecutor(max_workers=6)

logger = get_logger("Stepper")

class StepperMotor:
    def __init__(self, motor_id, name, step_pin, direction_pin=None, 
                 enable_pin=None, gpio=None):
        self.motor_id = motor_id
        self.name = name
        self.step_pin = step_pin
        self.direction_pin = direction_pin
        self.enable_pin = enable_pin
        self.gpio = gpio
        
        # Current state
        self.position = 0  # in steps
        self.target_position = 0
        self.is_moving = False
        self.enabled = False
        
        # Setup pins
        if self.gpio:
            self.gpio.setup_output(self.step_pin)
            if self.direction_pin:
                self.gpio.setup_output(self.direction_pin)
            if self.enable_pin:
                self.gpio.setup_output(self.enable_pin)
                self.disable()  # Start disabled
        
        logger.info(f"Stepper motor {motor_id} ({name}) initialized on pin {step_pin}")

    def enable(self):
        if self.enable_pin and self.gpio:
            self.gpio.write_pin(self.enable_pin, GPIO.LOW)  # Active low for many drivers
            self.enabled = True
            logger.debug(f"Motor {self.motor_id} enabled")

    def disable(self):
        if self.enable_pin and self.gpio:
            self.gpio.write_pin(self.enable_pin, GPIO.HIGH)
            self.enabled = False
            logger.debug(f"Motor {self.motor_id} disabled")

    def set_direction(self, direction):
        """Set direction: True for forward, False for reverse"""
        if self.direction_pin and self.gpio:
            self.gpio.write_pin(self.direction_pin, GPIO.HIGH if direction else GPIO.LOW)

    def move_steps_async(self, steps, direction=True, speed_delay=0.001):
        
            self.move_steps(steps, direction, speed_delay)
        
    """
    def move_steps(self, steps, direction=True, speed_delay=0.001):
        #Move specified number of steps
        if not self.enabled:
            self.enable()
        
        self.set_direction(direction)
        self.is_moving = True
        
        logger.info(f"Motor {self.motor_id}: Moving {steps} steps {'forward' if direction else 'reverse'}")
        
        for _ in range(abs(steps)):
            if not self.is_moving:  # Allow emergency stop
                break
            self.gpio.pulse(self.step_pin, speed_delay)
            self.position += 1 if direction else -1
            
        self.is_moving = False
        self.disable()
        logger.debug(f"Motor {self.motor_id}: Move completed. Position: {self.position}")

        return True
    """


    def move_steps(self, steps, direction=True, speed_delay=0.001):
        # ensure the motor is enabled and the direction is set before
        # generating any pulses; this mirrors the behaviour of the legacy
        # implementation and guarantees the driver receives an `enable`
        # pulse if required.
        if not self.enabled:
            self.enable()

        self.set_direction(direction)
        self.is_moving = True
        logger.info(f"Motor {self.motor_id}: Moving {steps} steps {'forward' if direction else 'reverse'}")

        mask = 1 << self.step_pin
        micros = int(speed_delay * 1_000_000)

        pulses = []
        for _ in range(abs(steps)):
            if not self.is_moving:  # allow the stop() method to interrupt
                break
            pulses.append(pigpio.pulse(mask, 0, micros))
            pulses.append(pigpio.pulse(0, mask, micros))
            self.position += 1 if direction else -1

        pi = self.gpio.pi
        pi.wave_clear()
        pi.wave_add_generic(pulses)
        wid = pi.wave_create()
        if wid >= 0:
            pi.wave_send_once(wid)
            # wait for transmission to finish or for stop
            while pi.wave_tx_busy() and self.is_moving:
                time.sleep(0.001)
            pi.wave_delete(wid)

        self.is_moving = False
        self.disable()
        logger.debug(f"Motor {self.motor_id}: Move completed. Position: {self.position}")

    def move_distance(self, distance_mm, direction=True, speed_delay=0.001):
        """Move specified distance in mm"""
        steps = int(distance_mm * self.steps_per_mm)
        self.move_steps(steps, direction, speed_delay)

    def home(self, home_pin=None, max_steps=10000, speed_delay=0.001):
        """Home the motor using limit switch"""
        if home_pin and self.gpio:
            self.gpio.setup_input(home_pin, GPIO.PUD_UP)
            self.set_direction(False)  # Move towards home
            
            for _ in range(max_steps):
                if self.gpio.read_pin(home_pin) == GPIO.LOW:  #Switch triggered
                    self.position = 0
                    logger.info(f"Motor {self.motor_id} homed")
                    return True
                self.gpio.pulse(self.step_pin, speed_delay)
            
            logger.warning(f"Motor {self.motor_id} failed to find home")
            return False
        
        return None

    def stop(self):
        """Emergency stop"""
        self.is_moving = False
        logger.warning(f"Motor {self.motor_id} stopped")

    def get_position_mm(self):
        """Get position in mm"""
        return self.position / self.steps_per_mm
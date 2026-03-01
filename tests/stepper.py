import json
import time
import sys
import signal
import RPi.GPIO as GPIO


class StepperMotor:
    def __init__(self, config_file):
        self.load_config(config_file)
        self.setup_gpio()

    def load_config(self, config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)

        self.step_pin = config["step_pin"]
        print(f"step_pin   = {self.step_pin}")
        self.dir_pin = config["dir_pin"]
        self.enable_pin = config["enable_pin"]
        self.step_delay = config["step_delay"]
        self.test_steps = config["test_steps"]

    def setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.setup(self.enable_pin, GPIO.OUT)

        GPIO.output(self.enable_pin, GPIO.LOW)  # Enable driver
        print("GPIO initialized")

    def move_steps(self, steps, direction=True):
        #GPIO.output(self.dir_pin, GPIO.HIGH if direction else GPIO.LOW)
        
        while True : 
            GPIO.output(self.enable_pin, GPIO.HIGH)
        """
        for _ in range(10):
            for _ in range(steps):
                GPIO.output(self.step_pin, GPIO.HIGH)
                print("ouput HIGH")
                time.sleep(self.step_delay)
                GPIO.output(self.step_pin, GPIO.LOW)
                print("ouput LOW")
                time.sleep(self.step_delay)
            
            time.sleep(0.5)
        """

    def disable(self):
        GPIO.output(self.enable_pin, GPIO.HIGH)

    def cleanup(self):
        self.disable()
        GPIO.cleanup()
        print("GPIO cleaned up safely")


def signal_handler(sig, frame):
    print("\nInterrupted! Cleaning up...")
    motor.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    motor = StepperMotor("config.json")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        print("Testing Stepper Motor")

        print("Moving Forward...")
        motor.move_steps(motor.test_steps, direction=True)

        time.sleep(1)

        print("Moving Reverse...")
        motor.move_steps(motor.test_steps, direction=False)

        print("Test Completed")

    except Exception as e:
        print("Error:", e)

    finally:
        motor.cleanup()

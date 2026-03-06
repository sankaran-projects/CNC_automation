import time
import pigpio
import smbus2
import struct
import RPi.GPIO as GPIO
from libraries.logger import get_logger

STM_I2C_ADDRESS = 0x08  # Change to your STM slave address
bus = smbus2.SMBus(1)

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

    def _run_motor_pwm(self, frequency, steps, direction, stop_event=None):
        pin = self.step_pin
        pi = self.gpio.pi
        self.is_moving = True
        
        logger.info(f"Motor {self.motor_id}: Starting - {steps} steps at {frequency} Hz")
        
        period_micros = int(1_000_000 / frequency)

        total_duration_us = steps * period_micros
        total_duration_s = total_duration_us / 1_000_000
        print(f"Total pulse duration: {total_duration_us/1000:.1f}ms ({total_duration_us}µs)")

        try:
            pi.hardware_PWM(pin, frequency, 500000)
            print(f"Hardware PWM started on GPIO {pin} ({frequency} Hz, 50% duty)")
        
            print(f" Hardware transmitting for {total_duration_s:.4f}s...")
            elapsed = 0
            check_interval = 0.001  # 1ms check interval
            last_log = 0
            
            while elapsed < total_duration_s:
                if stop_event and stop_event.is_set():
                    print(f" Stop signal received after {elapsed:.4f}s")
                    pi.hardware_PWM(pin, frequency, 0)  # Stop PWM (0% duty)
                    return int(steps * (elapsed / total_duration_s))
                
                # Log progress every 0.1s
                if elapsed - last_log >= 0.1:
                    percent = (elapsed / total_duration_s) * 100
                    print(f"  {percent:.0f}% ({elapsed:.3f}s / {total_duration_s:.3f}s)")
                    last_log = elapsed
                
                time.sleep(check_interval)
                elapsed += check_interval
            
            # Stop the hardware PWM - set duty cycle to 0%
            pi.hardware_PWM(pin, frequency, 0)
            print(f" Hardware PWM complete ({total_duration_s:.4f}s elapsed)")
            
        
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f" Connection error: {e}")
            return 0
        except Exception as e:
            print(f" Unexpected error: {e}")
            return 0
        
        self.is_moving = False
        self.disable()
        logger.debug(f"Motor {self.motor_id}: Completed. Position: {self.position}")

    def move_steps_async(self, steps, direction=True,  stop_event=None):
        self.set_direction(direction)
        if not self.enabled:
            self.enable()
        
        frequency = int(steps / 60)  # 60 second default speed
        self._run_motor_pwm(frequency, steps, direction, stop_event=stop_event)

    def send_data_to_stm(self, ml, dispense_time_sec=60, command="ON"):
        
        total_steps = int(ml)
        frequency = int(total_steps / dispense_time_sec)
        motor_id = self.motor_id
        command = command.upper()
        print("Total Steps:", total_steps)
        print("Frequency:", frequency)

        # Pack into 8 bytes (big endian) - total_steps, frequency, motor_id, command
        data = struct.pack(">IIIB", total_steps, frequency, motor_id, ord(command[0]))

        # Convert to list of bytes for I2C
        byte_list = list(data)

        # Send command to STM
        bus.write_i2c_block_data(STM_I2C_ADDRESS, 0x01, byte_list)
        print("Command sent to STM")

        # Poll for completion status
        max_attempts = 300  # 30 seconds max (100ms * 300)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Read status from STM (assuming 1 byte status response)
                status_data = bus.read_i2c_block_data(STM_I2C_ADDRESS, 0x02, 1)
                status = status_data[0]
                
                print(f"Status check {attempt + 1}: {status}")
                
                if status == 0x01:  # Completed successfully
                    print("STM operation completed successfully")
                    return True
                elif status == 0x02:  # Error
                    print("STM operation failed with error")
                    return False
                elif status == 0x00:  # Still running
                    pass  # Continue polling
                    
            except Exception as e:
                print(f"Error reading status from STM: {e}")
                return False
            
            time.sleep(0.1)  # Wait 100ms before next check
            attempt += 1
        
        print("STM operation timed out")
        return False


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

import threading
import time 
import json 
import signal
import sys
import RPi.GPIO as GPIO

from libraries.gpio_control import GPIOController
from libraries.dwin_display import DwinDisplay
from libraries.stepper import StepperMotor
from libraries.logger import get_logger
from libraries.input_handler import uart_listener, STATE, update_queue
from libraries.pump_controller import PumpController
from libraries.motor_processor import MotorProcessor
from libraries.state_manager import StateManager 
from libraries.rps_controller import RPSController



logger = get_logger("MAIN")

dirty_flag = threading.Event()


class MainController:
    """Main application controller - handles initialization and orchestration"""
    
    def __init__(self):
        self.running = True
        self.config_file = "config.json"
        self.steppers = []
        self.gpio = None
        self.dwin = None
        self.pump_controller = None
        self.state_manager = StateManager()
        self.rps_controller = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                return config
        except FileNotFoundError:
            logger.warning(f"Configuration file {self.config_file} not found. Using defaults.")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file: {e}")
            return {}
    
    def initialize(self):
        """Initialize all components"""
        try:
            # Load configuration
            config = self.load_config()
            
            # Initialize GPIO
            self.gpio = GPIOController()
            
            # Initialize DWIN display
            serial_config = config.get("serial", {"port": "/dev/ttyS0", "baudrate": 115200})
            self.dwin = DwinDisplay(
                port=serial_config["port"],
                baudrate=serial_config["baudrate"]
            )
            
            # Initialize stepper motors from config
            stepper_configs = config.get("stepper_motors", [])
            for motor_config in stepper_configs:
                try:
                    motor = StepperMotor(
                        motor_id=motor_config["id"],
                        name=motor_config["name"],
                        step_pin=motor_config["step_pin"],
                        direction_pin=motor_config.get("direction_pin"),
                        enable_pin=motor_config.get("enable_pin"),
                        gpio=self.gpio
                    )
                    self.steppers.append(motor)
                    logger.info(f"Motor {motor_config['id']} configured on pin {motor_config['step_pin']}")
                except Exception as e:
                    logger.error(f"Failed to configure motor {motor_config.get('id', 'unknown')}: {e}")
                    self.steppers.append(None)
            
            # Ensure we have exactly 6 motor slots
            while len(self.steppers) < 6:
                self.steppers.append(None)
            
            
            self.rps_controller = RPSController(config['RPS'])

            # Initialize pump controller
            self.pump_controller = PumpController(self.steppers, self.rps_controller, self.state_manager, dirty_flag, self.dwin, config.get("Configure_Steps", 0))

            
            # Start UART listener thread
            threading.Thread(
                target=uart_listener,
                args=(self.state_manager, self.dwin, self.steppers, dirty_flag),
                daemon=True
            ).start()
            
            # Start motor processor thread
            processor = MotorProcessor(self.pump_controller, dirty_flag, self)
            threading.Thread(
                target=processor.process_queue,
                args=(update_queue,),
                daemon=True
            ).start()
            
            # Load previous state
            self.state_manager.load_state(self.dwin, STATE)
            
            # Start background state save worker
            self.state_manager.start_save_worker(STATE, dirty_flag)

            self.dwin.page_switch(1)  # Switch to main page on DWIN
            time.sleep(0.1)
            
            common_relay_pin = config.get("Common_Relay", 20)
            # Setting the Relay HIGH due to current increases while booting
            self.gpio.setup_output(common_relay_pin)  # Example: Set pin 20 high on startup
            time.sleep(0.1)
            self.gpio.write_pin(common_relay_pin, GPIO.HIGH)
            print(f"Relay pin 20 set to HIGH on startup")
            time.sleep(0.1)

            
            logger.info("System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    def run(self):
        """Main application loop"""
        if not self.initialize():
            logger.error("Failed to initialize system")
            return
        
        logger.info("Main controller started")
        
        # Keep application running
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.running = False
            logger.info("Shutdown complete")




def main():
    """Entry point for the application"""
    controller = MainController()
    controller.run()


if __name__ == "__main__":
    main()

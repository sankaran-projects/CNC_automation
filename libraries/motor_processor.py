"""
Motor command processor module
Handles processing of motor commands from the input queue
"""

import queue
from libraries.logger import get_logger
from concurrent.futures import ThreadPoolExecutor

logger = get_logger("MotorProcessor")


class MotorProcessor:
    """Processes motor commands from the input queue"""
    
    def __init__(self, pump_controller, dirty_flag, running_flag):
        """
        Initialize motor processor
        
        Args:
            pump_controller: PumpController instance for controlling motors
            dirty_flag: Threading event flag to signal state changes
            running_flag: Should be an object with a 'running' attribute
        """
        self.pump_controller = pump_controller
        self.dirty_flag = dirty_flag
        self.running_flag = running_flag
        self.executor = ThreadPoolExecutor(max_workers=6)
    
    def process_queue(self, update_queue):
        """
        Process commands from the update queue
        
        Args:
            update_queue: Queue containing (motor_name, state_data) tuples
        """
        while self.running_flag.running:
            try:
                motor_name, state_data = update_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            logger.info(f"[Processor] {motor_name} updated: {state_data}")
            print(f"[Processor] {motor_name} updated: {state_data}")
            
            self._handle_command(motor_name, state_data)
            
            # Mark state as dirty for saving
            self.dirty_flag.set()
    
    def _handle_command(self, motor_name, state_data):
        """
        Route command to appropriate handler
        
        Args:
            motor_name: Name of the motor/RPS device
            state_data: Command data dictionary
        """
        command = state_data.get("command", "OFF")
        
        # Handle pump motor commands (m_1 through m_6)
        if motor_name.startswith("m_"):
            if command == "ON":
                logger.info(f"--> Starting {motor_name}")
                self.executor.submit(self.pump_controller.start_pump,
                    motor_name,
                    state_data
                    )
                #self.pump_controller.start_pump(motor_name, state_data)
            elif command == "OFF":
                logger.info(f"--> Stopping {motor_name}")
                self.executor.submit(
                self.pump_controller.stop_pump,
                        motor_name
                    )
                
        # Handle RPS commands (RPS_1 through RPS_3)
        elif motor_name.startswith("RPS_"):
            if command == "ON":
                logger.info(f"--> Starting {motor_name}")
                #self.pump_controller.start_RPS(motor_name, state_data)
                self.executor.submit(
                    self.pump_controller.start_RPS,
                    motor_name,
                    state_data
                )
            
            elif command == "OFF":
                logger.info(f"--> Stopping {motor_name}")
                self.executor.submit(
                    self.pump_controller.stop_RPS,
                    motor_name
                )
        
        else:
            logger.warning(f"Unknown motor type: {motor_name}")

"""
Pump and RPS (Rotary Pump System) control module
"""

from libraries.logger import get_logger
from libraries.input_handler import STATE 
import time

logger = get_logger("PumpController")

# Pump specifications
"""
PUMP_SPECS 
    Peristaltic Pump Specifications:
    - Motor: Stepper motor with external stepper driver
    - Rated voltage: 24V
    - Power: 20W
    - Motor speed: 350 RPM
    - Flow range: 32-110 ml/min (depends on tube size)
    - Tube types:
        S14 (1.6*4.8mm) → 32 ml/min
        S19 (2.4*5.6mm) → 70 ml/min
        S16 (3.2*6.4mm) → 110 ml/min
"""

class PumpController:
    """Controls peristaltic pumps and RPS systems"""
    
    def __init__(self, steppers, rps_controller, state_manager, dirty_flag, dwin, configure_steps=0):
        """
        Initialize pump controller
        
        Args:
            steppers: List of StepperMotor objects
        """
        self.steppers = steppers
        self.rps_controller = rps_controller
        self.state_manager = state_manager
        self.dirty_flag = dirty_flag
        self.configure_steps = configure_steps
        self.dwin = dwin
    
    def start_pump(self, motor_name, state_data):
        """
        Start a peristaltic pump motor
        
        Args:
            motor_name: Motor identifier (e.g., "m_1")
            state_data: Dictionary containing pump configuration and value
        """
        print(f"Starting Pump: {motor_name}")
        logger.info(f"Starting pump: {motor_name}")
        
        try:
            # Extract motor index (m_1 -> 0, m_2 -> 1, etc.)
            motor_index = int(motor_name.split('_')[1]) - 1
            
            if not (0 <= motor_index < len(self.steppers)):
                logger.error(f"Invalid motor index: {motor_name}")
                return
            
            stepper_obj = self.steppers[motor_index]
            if not stepper_obj:
                logger.error(f"Motor {motor_name} not initialized")
                return
            
            # Process and run motor
            value = int(state_data.get("value", 0))

            if value <= 0 or value > 1000 :
                logger.error(f"Invalid value for {motor_name}: {value}")
                self.dwin.page_switch(6)  # Switch to error page on DWIN
                time.sleep(1)
                self.dwin.page_switch(1) # Returning to main page
                return
            steps = int(STATE["config"].configure_steps) * value

            print(f"pump controller ------ steps : {steps}")
            
            STATE[motor_name].flag = "SET"

            stepper_obj.move_steps_async(steps, direction=True)
            

            STATE[motor_name].flag = "UNSET"

            self.state_manager.save_state(STATE, dirty_flag=self.dirty_flag)
            
            logger.info(f"Pump {motor_name} completed")
            

        except (ValueError, IndexError) as e:
            logger.error(f"Error processing motor name '{motor_name}': {e}")
        except Exception as e:
            logger.error(f"Error starting pump {motor_name}: {e}")
    
    def stop_pump(self, motor_name):
        """
        Stop a peristaltic pump motor
        
        Args:
            motor_name: Motor identifier (e.g., "m_1")
        """
        print(f"Stopping Pump: {motor_name}")
        logger.info(f"Stopping pump: {motor_name}")
        
        try:
            # Extract motor index (m_1 -> 0, m_2 -> 1, etc.)
            motor_index = abs(int(motor_name.split('_')[1]) - 1)
            
            if not (0 <= motor_index < len(self.steppers)):
                logger.error(f"Invalid motor index: {motor_name}")
                return
            
            stepper_obj = self.steppers[motor_index]
            
            if stepper_obj and stepper_obj.is_moving:
                print("inside is moving ")
                
                stepper_obj.is_moving = False
                stepper_obj.disable()
                if STATE[motor_name].flag == "SET":
                    STATE[motor_name].flag = "UNSET"
                    self.state_manager.save_state(STATE, dirty_flag=self.dirty_flag)
                logger.info(f"Pump {motor_name} stopped")
            
        except (ValueError, IndexError) as e:
            logger.error(f"Error processing motor name '{motor_name}': {e}")
        except Exception as e:
            logger.error(f"Error stopping pump {motor_name}: {e}")
    
    def start_RPS(self, rps_name, state_data):
        """
        Start RPS (Rotary Pump System)
        
        Args:
            rps_name: RPS identifier (e.g., "RPS_1")
            state_data: Dictionary containing RPS configuration
        """
        print(f"Starting RPS: {rps_name}")
        logger.info(f"Starting RPS: {rps_name}")
        volt_status = None
        current_status = None
        on_off_status = None

        try:
            if state_data.get("volt") is None or state_data.get("amps") is None:
                print(f"inside volt and amps none ----- ")
                logger.error(f"Voltage and current must be specified for {rps_name}")
                self.dwin.page_switch(6)  # Switch to error page on DWIN
                time.sleep(1)
                self.dwin.page_switch(1) # Returning to main page
                return
            # Extract motor index (m_1 -> 0, m_2 -> 1, etc.)
            rps_index = int(rps_name.split('_')[1]) - 1
            rps_index += 1
            print(f"RPS index: {rps_index}, Voltage: {state_data.get('volt')}, Current: {state_data.get('amps')}")
            if rps_index:
                print(f"inside rps index ----- {rps_index}")
                volt_status = self.rps_controller.set_voltage(rps_index, state_data.get("volt"))
            if volt_status:
                print(f"Voltage set successfully for {rps_name}")
                current_status = self.rps_controller.set_current(rps_index, state_data.get("amps"))
            if current_status:
                print(f"Current set successfully for {rps_name}")
                STATE[rps_name].flag = "SET"
                on_off_status = self.rps_controller.output_on(rps_index)
                print(f"Output on status for {rps_name}: {on_off_status}")
                STATE[rps_name].flag = "UNSET"
                self.state_manager.save_state(STATE, dirty_flag=self.dirty_flag)

            if on_off_status:
                return True
            else:
                return False
        
        except Exception as e:
            logger.error(f"Error turning on output for RPS {rps_index}: {str(e)}")
            return False
    
    def stop_RPS(self, rps_name):
        """
        Stop RPS (Rotary Pump System)
        
        Args:
            rps_name: RPS identifier (e.g., "RPS_1")
        """
        print(f"Stopping RPS: {rps_name}")
        logger.info(f"Stopping RPS: {rps_name}")

        try:
            # Extract motor index (m_1 -> 0, m_2 -> 1, etc.)
            rps_index = int(rps_name.split('_')[1]) - 1
            rps_index +=1
            self.rps_controller.output_off(rps_index)

            if STATE[rps_name].flag == "SET":
                    STATE[rps_name].flag = "UNSET"
                    self.state_manager.save_state(STATE, dirty_flag=self.dirty_flag)
        except Exception as e:
            logger.error(f"Error turning off output for RPS {rps_index}: {str(e)}")
            return False

       

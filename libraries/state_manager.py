"""
State management module
Handles loading, saving, and persisting application state
"""

import json
import time
import threading, os
from dataclasses import asdict
from libraries.logger import get_logger
from libraries.input_handler import Cmd, lock
 

logger = get_logger("StateManager")


class StateManager:
    """Manages application state persistence"""
    
    def __init__(self, state_file="state.json"):
        """
        Initialize state manager
        
        Args:
            state_file: Path to state file
        """
        self.state_file = state_file

    def _update_dwin_display(self, dwin, name, state_obj): 
        """Update DWIN display with current state values"""
        value_map = {
            "m_1": Cmd.MOTOR_CTRL,
            "RPS_1": Cmd.RPS_CTRL,
            
            "m_1_value": Cmd.MOTOR_1_VALUE,
            "m_2_value": Cmd.MOTOR_2_VALUE,
            "m_3_value": Cmd.MOTOR_3_VALUE,
            "m_4_value": Cmd.MOTOR_4_VALUE,
            "m_5_value": Cmd.MOTOR_5_VALUE,
            "m_6_value": Cmd.MOTOR_6_VALUE,

            "RPS_1_volt": Cmd.RPS_1_VOLT,
            "RPS_2_volt": Cmd.RPS_2_VOLT,
            "RPS_3_volt": Cmd.RPS_3_VOLT,

            "RPS_1_amps": Cmd.RPS_1_AMPS,
            "RPS_2_amps": Cmd.RPS_2_AMPS,
            "RPS_3_amps": Cmd.RPS_3_AMPS,

            "configure_steps": Cmd.Configure_Steps
        }

        try : 
            for mapped_name, address in value_map.items():
                # Only update the current device
                if mapped_name != name:
                    continue

                # -----------------------
                # Handle configure_steps
                # -----------------------
                if name == "configure_steps":
                    if state_obj not in ("", None):
                        dwin.send_value(address, state_obj)
                    return
                
                # -----------------------
                # Send BUTTON STATE (if exists)
                # -----------------------
                if hasattr(state_obj, "button_state") and state_obj.button_state:
                    dwin.send_value(address, state_obj.button_state)
                else:
                    dwin.send_value(address, 0)  # Send 0 if no button state
                
                # -----------------------
                # Send VALUE (Motor / RPS)
                # -----------------------
                if hasattr(state_obj, "value") and state_obj.value not in ("", None):
                    if mapped_name.startswith("m_") and not mapped_name.endswith("_value"):
                        for mapped_name, address in value_map.items():
                            if mapped_name == f"{name}_value":
                                value_address = address
                                dwin.send_value(value_address, state_obj.value)
                    if mapped_name.startswith("RPS_") and not (mapped_name.endswith("_volt") or mapped_name.endswith("_amps")):
                        for mapped_name, address in value_map.items():
                            if mapped_name.startswith(name) and mapped_name.endswith("_volt"):
                                value_address = address
                                dwin.send_value(value_address, state_obj.value)
                            if mapped_name.startswith(name) and mapped_name.endswith("_amps"):
                                value_address = address
                                dwin.send_value(value_address, state_obj.value)

                break  # Stop after match

        except Exception as e:
            logger.error(f"DWIN restore failed for {name}: {e}")


    
    def load_state(self, dwin, STATE):
        """
        Load state from file
        
        Args:
            STATE: Dictionary of motor states to load into
        """
        try:

            if not os.path.exists(self.state_file):
                logger.info("No previous state file found, starting fresh.")
                return

            with open(self.state_file, "r") as f:
                saved = json.load(f)

                # hold lock while mutating STATE to avoid races with other
                # threads (e.g. save worker or pump controller)
                with lock:
                    for name, data in saved.items(): # "m_1": {MotorState data}"
                        if name in STATE:

                            # ----------------------------
                            # Update DWIN Display
                            # ----------------------------
                            self._update_dwin_display(dwin, name, STATE[name]) # "m_1" , object

                            
                            # Update internal state
                            if name != "config": 
                                if STATE[name].flag == "SET":
                                    STATE[name].update(**data)

                logger.info("State loaded from file.")
        except FileNotFoundError:
            logger.info("No previous state file found, starting fresh.")
        except json.JSONDecodeError as e:
            logger.error(f"Error reading state file: {e}")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    def save_state(self, STATE, dirty_flag):
        """
        Save state to file
        
        Args:
            STATE: Dictionary of motor states to save
            dirty_flag: Threading event flag to clear after saving
        """
        try:
            # serialise the state to prevent concurrent writes/updates
            with lock:
                with open(self.state_file, "w") as f:
                    json.dump(
                        {name: asdict(motor) for name, motor in STATE.items()},
                        f,
                        indent=4
                    )
                dirty_flag.clear()
            logger.info("State saved to file.")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def start_save_worker(self, STATE, dirty_flag):
        """
        Start background thread that saves state when dirty_flag is set
        
        Args:
            STATE: Dictionary of motor states
            dirty_flag: Threading event flag indicating state changes
            
        Returns:
            threading.Thread: The started daemon thread
        """
        def save_worker():
            """Background worker that monitors dirty_flag"""
            while True:
                if dirty_flag.is_set():
                    self.save_state(STATE, dirty_flag)
                time.sleep(2)
        
        thread = threading.Thread(target=save_worker, daemon=True)
        thread.start()
        return thread

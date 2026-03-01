import json
from dataclasses import asdict, dataclass

class StateManager:

    state_file = "state.json"

    def save_state(STATE):
            """
            Save state to file
            
            Args:
                STATE: Dictionary of motor states to save
                dirty_flag: Threading event flag to clear after saving
            """
            try:
                with open("state.json", "w") as f:
                    json.dump(
                        {name: asdict(motor) for name, motor in STATE.items()},
                        f,
                        indent=4
                    )
                print("State saved to file.")
                
            except Exception as e:
                print(f"Error saving state: {e}")



@dataclass
class MotorState:
    name: str
    command: str = "OFF"
    flag: str = "UNSET"
    timestamp: str = ""
    button_state: int = 0
    value: int = 0


    def update(self, **kwargs):
        """ Update state and push changes to queue"""
        for key , val in kwargs.items():
            setattr(self, key, val)

        #update_queue.put((self.name, asdict(self)))

@dataclass
class RpsState:
    name: str
    command : str = "OFF"
    flag: str = "UNSET"
    timestamp: str = ""
    volt: int = ""
    amps: int = ""

    def update(self, **kwargs):
        """ Update state and push changes to queue"""
        for key , val in kwargs.items():
            setattr(self, key, val)

        #update_queue.put((self.name, asdict(self)))


STATE = {
        **{f"m_{i}": MotorState(f"m_{i}") for i in range(1, 7)},
        **{f"RPS_{i}": RpsState(f"RPS_{i}") for i in range(1, 4)},
        }

STATE["RPS_1"].volt = 25
STATE["RPS_1"].flag = "SET"
StateManager.save_state(STATE)
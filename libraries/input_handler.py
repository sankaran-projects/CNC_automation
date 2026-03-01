import json
import threading
from datetime import datetime
from libraries.logger import get_logger
from dataclasses import dataclass, asdict
import time
import queue

logger = get_logger("InputHandler")

# ================= DWIN ADDRESSES =================
# Button addresses
class Cmd : 
    STEPPER_ON = 0x1010
    STEPPER_OFF = 0x1011
    MOTOR_CTRL = 0x1000

    MOTOR_1_VALUE = 0x2000
    MOTOR_2_VALUE = 0x2002
    MOTOR_3_VALUE = 0x2004
    MOTOR_4_VALUE = 0x2006
    MOTOR_5_VALUE = 0x2008
    MOTOR_6_VALUE = 0x200A

    RPS_CTRL = 0x1000

    RPS_1_VOLT = 0x3000
    RPS_2_VOLT = 0x3002
    RPS_3_VOLT = 0x3004

    RPS_1_AMPS = 0x3006
    RPS_2_AMPS = 0x3008
    RPS_3_AMPS = 0x300A

    Configure_Steps = 0x4000





# ================= GLOBAL STATE =================

CONFIG_FILE = "config.json"
update_queue = queue.Queue()
lock = threading.Lock()



@dataclass
class MotorState:
    name: str
    command: str = "OFF"
    flag: str = "UNSET"
    timestamp: str = ""
    button_state: int = 0
    value: int = 0



    def update(self, **kwargs):
        """ Update state and push changes to queue.

        This method is called from multiple threads; hold the global
        `lock` while mutating fields and pushing the change so that no
        reader sees a half‑updated state.
        """
        with lock:
            for key , val in kwargs.items():
                setattr(self, key, val)
            update_queue.put((self.name, asdict(self)))

@dataclass
class RpsState:
    name: str
    command : str = "OFF"
    flag: str = "UNSET"
    timestamp: str = ""
    volt: int = ""
    amps: int = ""

    def update(self, **kwargs):
        """ Update state and push changes to queue.

        See :meth:`MotorState.update` for explanation about locking.
        """
        with lock:
            for key , val in kwargs.items():
                setattr(self, key, val)
            update_queue.put((self.name, asdict(self)))

@dataclass
class ConfigState:
    configure_steps: int = 0

STATE = {
        **{f"m_{i}": MotorState(f"m_{i}") for i in range(1, 7)},
        **{f"RPS_{i}": RpsState(f"RPS_{i}") for i in range(1, 4)},
        "config": ConfigState()
}



def load_config():
    """Load configuration from JSON file"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            logger.info("Configuration loaded successfully")
            return config
            
    except FileNotFoundError:
        logger.warning(f"Configuration file {CONFIG_FILE} not found. Using defaults.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing configuration file: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return {}


def uart_listener(dwin, motor_controllers=None):
    """Listen for commands from DWIN display"""
    logger.info("UART listener started")
    
    while dwin.running:
        if not dwin.connected:
            time.sleep(0.1)
            continue
            
        pkt = dwin.read_packet()
        
        if not pkt:
            time.sleep(0.01)
            continue

        try:
            print(f"packet ---- {pkt}")
            # Packet format: 5A A5 len cmd addrH addrL dataH dataL
            cmd = pkt[3]
            address = (pkt[4] << 8) | pkt[5]
            
            value = (pkt[7] << 8) | pkt[8] 

            print(f"value ---- {value} address: {address}")

            logger.debug(f"DWIN Packet - cmd: 0x{cmd:02X}, address: 0x{address:04X}, value: {value}")
            
            with lock:
                if cmd == 0x83:  # Write command from HMI
                    handle_hmi_command(address, value, motor_controllers)
                    
                logger.debug(f"DWIN Command: Addr=0x{address:04X}, Value={value}")
                
        except Exception as e:
            logger.error(f"Error processing DWIN packet: {e}")

def handle_hmi_command(address, value, motor_controllers):
    """Handle HMI commands based on address"""
    
    def update_on_off(state_key, value, command):
        """Update motor on/off state"""
        data = {
            "command": command,
            "button_state": value,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        STATE[state_key].update(**data)
    
    def update_motor_value(state_key, value):
        """Update motor value (preprocessed from string/ascii)"""
        if value:
            STATE[state_key].value = value

    def update_rps_value(state_key, field, value):

        if field == "volt":
            STATE[state_key].volt = value
        elif field == "amps":
            STATE[state_key].amps = value
    
    def configure_steps_fun(state_key, value):
        """Update steps per ml configuration"""
        print(f"Configuring steps per ml: {value}")
        if value:
            STATE["config"].configure_steps = value


    # Handle Motor and RPS control commands
    if address == Cmd.MOTOR_CTRL or address == Cmd.RPS_CTRL:
        bitmask = value
        temp = 0 
        print(f"bitmask ---- 0x{bitmask}")
        
        match address:

            case Cmd.MOTOR_CTRL:

                changed_bits = bitmask ^ temp

                for i in range(9):

                    # Check if THIS bit changed
                    if changed_bits & (1 << i):

                        # Determine name
                        if i < 6:
                            name = f"m_{i+1}"
                        else:
                            name = f"RPS_{i-5}"

                        # Check new state of bit
                        if bitmask & (1 << i):
                            update_on_off(name, value, command="ON")
                        else:
                            update_on_off(name, value, command="OFF")

                # After processing, update previous state
                temp = bitmask

    motor_value_map = {
        Cmd.MOTOR_1_VALUE: "m_1", Cmd.MOTOR_2_VALUE: "m_2", Cmd.MOTOR_3_VALUE: "m_3",
        Cmd.MOTOR_4_VALUE: "m_4", Cmd.MOTOR_5_VALUE: "m_5", Cmd.MOTOR_6_VALUE: "m_6",
    }
    
    rps_value_map = {
        Cmd.RPS_1_VOLT: ("RPS_1", "volt"),
        Cmd.RPS_2_VOLT: ("RPS_2", "volt"),
        Cmd.RPS_3_VOLT: ("RPS_3", "volt"),

        Cmd.RPS_1_AMPS: ("RPS_1", "amps"),
        Cmd.RPS_2_AMPS: ("RPS_2", "amps"),
        Cmd.RPS_3_AMPS: ("RPS_3", "amps"),
    }

    configure_value_map = {
        Cmd.Configure_Steps: "configure_steps"
    }
    
    
    # Handle motor value commands
    if address in motor_value_map:
        typecasted_value = int(value)
        print(f"original value ---------- : {value}, typecasted value ---- {typecasted_value}")
        update_motor_value(motor_value_map[address], typecasted_value)

    # Handle RPS value commands
    elif address in rps_value_map:
        state_key, field = rps_value_map[address]
        typecasted_value = float(value) 
        update_rps_value(state_key, field, value)

    # Handle COnfigure steps command
    elif address in configure_value_map:
        state_key = configure_value_map[address]
        configure_steps_fun(state_key, value)
    else:
        logger.warning(f"Unknown command address: 0x{address:04X}")
        

        
        

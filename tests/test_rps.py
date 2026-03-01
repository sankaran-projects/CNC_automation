"""
RPS (Remote Power Supply) Control and Test Script
Uses PyVISA to communicate with RPS units
"""

import sys
import os
import json
import time
import pyvisa
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libraries.logger import get_logger
logger = get_logger("RPS")

class RPSController:
    """Controls multiple RPS units via PyVISA"""

    def __init__(self, rps_config):
        """
        Initialize RPS controller with multiple units
        Args:
            rps_config: List of RPS configuration dicts from config.json
        """
        self.rps_config = rps_config
        self.rps_units = {}
        self.rm = pyvisa.ResourceManager()
        logger.info(f"Initializing RPS Controller with {len(rps_config)} units")
        self._initialize_rps_units()

    def _initialize_rps_units(self):
        """Initialize all RPS units from configuration"""
        for rps in self.rps_config:
            try:
                rps_id = rps.get("id")
                rps_name = rps.get("name")
                usb_port = rps.get("usb_port")

                resource_string = f"ASRL{usb_port}::INSTR"
                logger.info(f"Connecting to {rps_name} on port {usb_port}")

                instrument = self.rm.open_resource(resource_string)
                instrument.baud_rate = 115200
                instrument.timeout = 2000

                self.rps_units[rps_id] = {
                    "name": rps_name,
                    "instrument": instrument,
                    "usb_port": usb_port
                }
                logger.info(f"Connected to {rps_name} (ID: {rps_id})")

            except Exception as e:
                logger.error(f"Failed to init {rps.get('name')}: {str(e)}")

    def get_rps_status(self, rps_id):
        """Get voltage, current, and output status"""
        try:
            if rps_id not in self.rps_units:
                logger.warning(f"RPS ID {rps_id} not found")
                return None

            instrument = self.rps_units[rps_id]["instrument"]

            voltage = instrument.query("VOUT?").strip()
            current = instrument.query("IOUT?").strip()
            output_status = instrument.query("OUTP?").strip()

            status = {
                "rps_id": rps_id,
                "name": self.rps_units[rps_id]["name"],
                "voltage": float(voltage) if voltage else 0.0,
                "current": float(current) if current else 0.0,
                "output_enabled": bool(int(output_status))
            }
            logger.info(f"RPS {rps_id} Status: V={status['voltage']}V, I={status['current']}A, Output={status['output_enabled']}")
            return status

        except Exception as e:
            logger.error(f"Error getting status for RPS {rps_id}: {str(e)}")
            return None

    def set_voltage(self, rps_id, voltage):
        """Set voltage"""
        try:
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write(f"VSET {voltage}")
            logger.info(f"Set RPS {rps_id} voltage to {voltage}V")
            return True
        except Exception as e:
            logger.error(f"Error setting voltage: {str(e)}")
            return False

    def set_current(self, rps_id, current):
        """Set current limit"""
        try:
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write(f"ISET {current}")
            logger.info(f"Set RPS {rps_id} current limit to {current}A")
            return True
        except Exception as e:
            logger.error(f"Error setting current: {str(e)}")
            return False

    def output_on(self, rps_id):
        """Turn output ON"""
        try:
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write("OUTP 1")
            logger.info(f"Output ON for RPS {rps_id}")
            return True
        except Exception as e:
            logger.error(f"Error turning ON output: {str(e)}")
            return False

    def output_off(self, rps_id):
        """Turn output OFF"""
        try:
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write("OUTP 0")
            logger.info(f"Output OFF for RPS {rps_id}")
            return True
        except Exception as e:
            logger.error(f"Error turning OFF output: {str(e)}")
            return False

    def shutdown_all(self):
        """Turn off all RPS units and close connections"""
        for rps_id in self.rps_units:
            self.output_off(rps_id)
            self.rps_units[rps_id]["instrument"].close()
            logger.info(f"Closed connection to RPS {rps_id}")
        self.rm.close()
        logger.info("All RPS connections closed")

class RPSTester:
    """Test RPS communication and control"""

    def __init__(self, config_path="config.json"):
        self.config = None
        self.rps_controller = None
        self.load_config(config_path)

    def load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Config loaded from {config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def initialize_rps(self):
        if not self.config or 'RPS' not in self.config:
            print("No RPS config found")
            return False
        self.rps_controller = RPSController(self.config['RPS'])
        return True

    def run_demo(self):
        """Demo: set voltage/current and read back"""
        for rps_id in self.rps_controller.rps_units:
            print(f"\n--- Testing RPS {rps_id} ---")
            self.rps_controller.set_voltage(rps_id, 5.0)
            self.rps_controller.set_current(rps_id, 2.0)
            self.rps_controller.output_on(rps_id)
            time.sleep(1)
            status = self.rps_controller.get_rps_status(rps_id)
            print(status)
            self.rps_controller.output_off(rps_id)

    def cleanup(self):
        if self.rps_controller:
            self.rps_controller.shutdown_all()

def main():
    tester = RPSTester("config.json")
    if tester.initialize_rps():
        tester.run_demo()
        tester.cleanup()

if __name__ == "__main__":
    main()

"""
RPS (Remote Power Supply) control module using PyVISA
Handles communication and control of multiple RPS units
"""

import pyvisa
from libraries.logger import get_logger

logger = get_logger("RPSController")


class RPSController:
    """Controls multiple RPS units via PyVISA"""
    
    def __init__(self, rps_config):
        """
        Initialize RPS controller with multiple units
        
        Args:
            rps_config: List of RPS configuration dictionaries from config.json
                       Expected format: [{"id": 1, "name": "RPS 1", "usb_port": "/dev/ttyUSB0"}, ...]
        """
        self.rps_config = rps_config
        self.rps_units = {}
        self.rm = pyvisa.ResourceManager('@py')
        
        logger.info(f"Initializing RPS Controller with {len(rps_config)} units")
        self._initialize_rps_units()
    
    def _initialize_rps_units(self):
        """Initialize all RPS units from configuration"""
        for rps in self.rps_config:
            try:
                rps_id = rps.get("id")
                rps_name = rps.get("name")
                usb_port = rps.get("usb_port")
                
                logger.info(f"Connecting to {rps_name} on port {usb_port}")

                # Discover available VISA resources and pick the one matching usb_port
                resources = self.rm.list_resources()
                resource_name = None

                # prepare a search key for matching resources
                search_key = None
                if usb_port:
                    # strip any leading path components; we just want ttyUSBx or similar
                    search_key = str(usb_port).split('/')[-1]
                # default to matching any USB serial device
                if not search_key:
                    search_key = "ttyUSB"

                # If configuration already appears to be a full VISA string, just use it
                if usb_port and "::" in str(usb_port):
                    resource_name = usb_port
                else:
                    # search the listed resources for our key substring
                    for res in resources:
                        if search_key in res:
                            resource_name = res
                            break
                    # if still not found, as a last resort take the first ASRL resource
                    if resource_name is None:
                        for res in resources:
                            if str(res).upper().startswith("ASRL"):
                                resource_name = res
                                break

                if resource_name is None:
                    raise RuntimeError(f"Could not find VISA resource for port {usb_port}. Available: {resources}")

                # Open VISA connection
                instrument = self.rm.open_resource(resource_name)

                print(f"------- instrument: {instrument}")
                # Configure serial parameters
                instrument.baud_rate = 115200
                instrument.data_bits = 8
                instrument.parity = pyvisa.constants.Parity.none
                instrument.stop_bits = pyvisa.constants.StopBits.one

                instrument.read_termination = '\n'
                instrument.write_termination = '\n'
                instrument.timeout = 2000

                # Probe instrument identity
                try:
                    idn = instrument.query("*IDN?")
                    print(f"Instrument ID: {idn}")
                    logger.info(f"{rps_name} ({resource_name}) IDN: {idn}")
                except Exception as idn_e:
                    logger.warning(f"Failed to query *IDN? for {rps_name} ({resource_name}): {idn_e}")
                
                # Store instrument with ID as key
                self.rps_units[rps_id] = {
                    "name": rps_name,
                    "instrument": instrument,
                    "usb_port": usb_port
                }
                
                logger.info(f"Successfully connected to {rps_name} (ID: {rps_id})")
                
            except Exception as e:
                logger.error(f"Failed to initialize {rps.get('name')}: {str(e)}")
    
    def get_rps_status(self, rps_id):
        """
        Get status of specific RPS unit
        
        Args:
            rps_id: RPS unit ID
            
        Returns:
            dict: Status information or None if failed
        """
        try:
            if rps_id not in self.rps_units:
                logger.warning(f"RPS ID {rps_id} not found")
                return None
            
            instrument = self.rps_units[rps_id]["instrument"]
            
            # Query voltage
            voltage = instrument.query("VOUT?")
            
            # Query current
            current = instrument.query("IOUT?")
            
            # Query output status
            output_status = instrument.query("OUTP?")
            
            status = {
                "rps_id": rps_id,
                "name": self.rps_units[rps_id]["name"],
                "voltage": float(voltage),
                "current": float(current),
                "output_enabled": bool(int(output_status))
            }
            
            logger.info(f"RPS {rps_id} Status: V={status['voltage']}V, I={status['current']}A, Output={status['output_enabled']}")
            return status
            
        except Exception as e:
            logger.error(f"Error getting status for RPS {rps_id}: {str(e)}")
            return None
    
    def set_voltage(self, rps_id, voltage):
        """
        Set voltage for specific RPS unit
        
        Args:
            rps_id: RPS unit ID
            voltage: Voltage value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("inside set voltage")
            if rps_id not in self.rps_units:
                logger.warning(f"RPS ID {rps_id} not found")
                return False
            
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write(f"VOLT {voltage}")
            
            logger.info(f"Set RPS {rps_id} voltage to {voltage}V")
            return True
            
        except Exception as e:
            logger.error(f"Error setting voltage for RPS {rps_id}: {str(e)}")
            return False
    
    def set_current(self, rps_id, current):
        """
        Set current limit for specific RPS unit
        
        Args:
            rps_id: RPS unit ID
            current: Current limit value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("inside set current")
            if rps_id not in self.rps_units:
                logger.warning(f"RPS ID {rps_id} not found")
                return False
            
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write(f"CURR {current}")
            
            logger.info(f"Set RPS {rps_id} current limit to {current}A")
            return True
            
        except Exception as e:
            logger.error(f"Error setting current for RPS {rps_id}: {str(e)}")
            return False
    
    def output_on(self, rps_id):
        """
        Turn output ON for specific RPS unit
        
        Args:
            rps_id: RPS unit ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if rps_id not in self.rps_units:
                logger.warning(f"RPS ID {rps_id} not found")
                return False
            
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write("OUTP ON")
            
            logger.info(f"Turned ON output for RPS {rps_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error turning on output for RPS {rps_id}: {str(e)}")
            return False
    
    def output_off(self, rps_id):
        """
        Turn output OFF for specific RPS unit
        
        Args:
            rps_id: RPS unit ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if rps_id not in self.rps_units:
                logger.warning(f"RPS ID {rps_id} not found")
                return False
            
            instrument = self.rps_units[rps_id]["instrument"]
            instrument.write("OUTP OFF")
            
            logger.info(f"Turned OFF output for RPS {rps_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error turning off output for RPS {rps_id}: {str(e)}")
            return False
    
    def shutdown_all(self):
        """Turn off all RPS units and close connections"""
        try:
            for rps_id in self.rps_units:
                self.output_off(rps_id)
                self.rps_units[rps_id]["instrument"].close()
                logger.info(f"Closed connection to RPS {rps_id}")
            
            self.rm.close()
            logger.info("All RPS connections closed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
    
    def get_all_rps_status(self):
        """
        Get status of all RPS units
        
        Returns:
            list: List of status dictionaries for all RPS units
        """
        all_status = []
        for rps_id in self.rps_units:
            status = self.get_rps_status(rps_id)
            if status:
                all_status.append(status)
        return all_status

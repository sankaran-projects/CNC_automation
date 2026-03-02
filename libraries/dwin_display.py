import serial
import threading
import time
from libraries.logger import get_logger

logger = get_logger("DWIN")

class DwinDisplay:
    def __init__(self, port="/dev/ttyS0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = True
        self.connected = False
        # receive buffer used by read_packet; any bytes that have been read
        # from the serial port but not yet formed into a complete DWIN packet
        # are kept here between calls.
        self._recv_buffer = bytearray()

        self.connect()

    def connect(self):
        """Connect to DWIN display"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.connected = True
            logger.info(f"Connected to DWIN display on {self.port}")
            
            # Send handshake/test command
            time.sleep(0.1)
            self.ser.flush()

        except Exception as e:
            logger.error(f"Failed to connect to DWIN display: {e}")
            self.connected = False

    def read_packet(self):
        """Return one complete DWIN packet, if available.

        This method reads all bytes currently waiting on the UART into a
        private buffer and then attempts to parse a single packet from that
        buffer.  If a full packet is found it is removed from the buffer and
        returned; otherwise ``None`` is returned and the partial data is kept
        until the next call.  The packet format is::

            0x5A 0xA5 <len> <...len bytes of payload...>

        where the length byte specifies the number of bytes that follow it.
        """
        if not self.connected or not self.ser:
            return None

        try:
            # read any new data into the receive buffer
            if self.ser.in_waiting:
                self._recv_buffer.extend(self.ser.read(self.ser.in_waiting))

            # need at least header
            if len(self._recv_buffer) < 3:
                return None

            # ensure sync bytes are in place; if not search for next possible
            # sync and discard any leading garbage
            if self._recv_buffer[0:2] != b"\x5A\xA5":
                idx = self._recv_buffer.find(b"\x5A\xA5", 1)
                if idx == -1:
                    # no sync sequence, drop everything
                    self._recv_buffer.clear()
                    return None
                # drop bytes before the sync sequence
                del self._recv_buffer[:idx]
                if len(self._recv_buffer) < 3:
                    return None

            length = self._recv_buffer[2]
            total_len = 3 + length
            if len(self._recv_buffer) < total_len:
                # wait for more bytes
                return None

            packet = bytes(self._recv_buffer[:total_len])
            del self._recv_buffer[:total_len]
            return packet

        except Exception as e:
            logger.error(f"Error reading from DWIN: {e}")
            self.reconnect()
            return None

    def send_value(self, address, value):
        """Send value to DWIN display variable address"""
        if not self.connected or not self.ser:
            logger.error("Cannot send: Not connected to DWIN")
            return False
            
        try:
            logger.debug(f"Sending to DWIN: Addr=0x{address:04X}, Value={value}")
            # Format: 5A A5 len 82 addrH addrL dataH dataL
            packet = bytearray([
                0x5A, 0xA5, 0x05, 0x82,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF
            ])
            self.ser.write(packet)
            self.ser.flush()
            logger.debug(f"Sent to DWIN: Addr=0x{address:04X}, Value={value}")
            return True
        except Exception as e:
            logger.error(f"Error sending to DWIN: {e}")
            self.reconnect()
            return False

    def page_switch(self, page_id):
        """Switch DWIN display page"""
        if not self.connected or not self.ser:
            logger.error("Cannot switch page: Not connected to DWIN")
            return False
            
        try:
            # Format: 5A A5 len 82 addrH addrL dataH dataL
            packet = bytearray([
                0x5A, 0xA5, 0x07, 0x82,
                0x00,  # Page switch address (example)
                0x84, 0x5A, 0x01, 
                (page_id >> 8),
                page_id & 0xFF
            ])
            self.ser.write(packet)
            self.ser.flush()
            logger.info(f"Switched DWIN to page {page_id}")
            return True
        except Exception as e:
            logger.error(f"Error switching DWIN page: {e}")
            self.reconnect()
            return False

    def send_string(self, address, text):
        """Send string to DWIN display text address"""
        if not self.connected or not self.ser:
            return False
            
        try:
            text_bytes = text.encode('gb2312')  # DWIN uses GB2312 encoding
            length = len(text_bytes) + 3
            packet = bytearray([
                0x5A, 0xA5, length, 0x82,
                (address >> 8) & 0xFF,
                address & 0xFF
            ])
            packet.extend(text_bytes)
            self.ser.write(packet)
            return True
        except Exception as e:
            logger.error(f"Error sending string to DWIN: {e}")
            return False

    def reconnect(self):
        """Attempt to reconnect to DWIN display"""
        self.close()
        time.sleep(1)
        self.connect()

    def close(self):
        """Close connection to DWIN display"""
        self.running = False
        self.connected = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("DWIN display connection closed")
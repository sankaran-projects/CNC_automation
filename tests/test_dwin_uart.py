"""
Test script to monitor DWIN display UART communication
Captures and displays incoming data from DWIN display
"""

import sys
import os
import serial
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libraries.logger import get_logger

logger = get_logger("TestDWINUART")


class DWINUARTTester:
    """Monitor and log DWIN UART communication"""
    
    def __init__(self, port="/dev/serial0", baudrate=115200):
        """Initialize UART tester"""
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = False
        # buffer for accumulating raw bytes so we can split into actual DWIN
        # packets. This mirrors the logic used in ``DwinDisplay`` and makes the
        # report of packets consistent with what the application sees.
        self._recv_buffer = bytearray()

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
            self.running = True
            logger.info(f"Connected to {self.port} at {self.baudrate} baud")
            print(f"✓ Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            print(f"✗ Connection failed: {e}")
            return False
    
    def parse_packet(self, data):
        """Parse and display packet information"""
        hex_str = ' '.join(f'{b:02X}' for b in data)
        print(f"  Hex:    {hex_str}")
        
        # Check for DWIN header
        if len(data) >= 3:
            if data[0:3] == b'\x5A\xA5\x05':
                print(f"  Type:   DWIN Response Packet")
                if len(data) >= 4:
                    cmd = data[3]
                    print(f"  Cmd:    0x{cmd:02X}")
                if len(data) >= 6:
                    addr = (data[4] << 8) | data[5]
                    print(f"  Addr:   0x{addr:04X}")
                if len(data) >= 9:
                    value = (data[6] << 8) | data[7]
                    print(f"  Value:  {value} (0x{value:04X})")
            elif data[0:3] == b'\x5A\xA5\x04':
                print(f"  Type:   DWIN Write Command")
        
        # Show as ASCII if printable
        try:
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
            print(f"  ASCII:  {ascii_str}")
        except:
            pass
    
    def _extract_packets(self):
        """Extract complete DWIN packets from the receive buffer.

        Returns a list of byte strings representing logical packets.  Any
        partial packet remains in ``self._recv_buffer`` for the next call.
        """
        packets = []
        buf = self._recv_buffer
        while True:
            if len(buf) < 3:
                break
            if buf[0:2] != b"\x5A\xA5":
                idx = buf.find(b"\x5A\xA5", 1)
                if idx == -1:
                    buf.clear()
                    break
                del buf[:idx]
                if len(buf) < 3:
                    break
            length = buf[2]
            total = 3 + length
            if len(buf) < total:
                break
            packets.append(bytes(buf[:total]))
            del buf[:total]
        return packets

    def monitor_uart(self, duration=60):
        """Monitor UART for incoming data"""
        if not self.ser or not self.running:
            print("Not connected!")
            return

        print(f"\n{'='*70}")
        print(f"DWIN UART Monitor Started - Monitoring for {duration} seconds")
        print(f"{'='*70}\n")

        start_time = time.time()
        packet_count = 0
        byte_count = 0

        try:
            while self.running and (time.time() - start_time) < duration:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    byte_count += len(data)
                    self._recv_buffer.extend(data)

                    # extract logical packets
                    pkts = self._extract_packets()
                    for pkt in pkts:
                        packet_count += 1
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] Packet #{packet_count} - {len(pkt)} bytes")
                        self.parse_packet(pkt)
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n\n⚠ Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            print(f"✗ Error during monitoring: {e}")
        finally:
            elapsed = time.time() - start_time
            print(f"\n{'='*70}")
            print(f"Monitor Summary:")
            print(f"  Duration:   {elapsed:.2f} seconds")
            print(f"  Packets:    {packet_count}")
            print(f"  Total Bytes: {byte_count}")
            if packet_count > 0:
                print(f"  Avg Size:   {byte_count/packet_count:.1f} bytes/packet")
            print(f"{'='*70}")
    
    def send_test_packet(self, address=0x0100, value=0x1234):
        """Send a test packet to DWIN display"""
        try:
            packet = bytearray([
                0x5A, 0xA5, 0x05, 0x82,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF
            ])
            
            hex_str = ' '.join(f'{b:02X}' for b in packet)
            print(f"\n[TEST] Sending test packet:")
            print(f"  Hex:    {hex_str}")
            print(f"  Addr:   0x{address:04X}")
            print(f"  Value:  {value}")
            
            self.ser.write(packet)
            self.ser.flush()
            print("  ✓ Sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send test packet: {e}")
            print(f"  ✗ Failed: {e}")
    
    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.running = False
            logger.info("UART connection closed")
            print("✓ Connection closed")


def main():
    """Main test function"""
    print("\n" + "="*70)
    print("DWIN Display UART Communication Tester")
    print("="*70 + "\n")
    
    # Use COM port for Windows, /dev/ttyS0 for Linux
    port = "/dev/serial0"  # Change this to your actual port
    baudrate = 115200
    
    print(f"Configuration:")
    print(f"  Port:       {port}")
    print(f"  Baudrate:   {baudrate}")
    print(f"\nNote: Modify 'port' variable to match your DWIN connection\n")
    
    tester = DWINUARTTester(port=port, baudrate=baudrate)
    
    if not tester.connect():
        return
    
    try:
        # Optional: Send a test packet
        tester.send_test_packet(address=0x3000, value=0xA040)
        # time.sleep(0.5)
        
        # Monitor for 60 seconds
        #tester.monitor_uart(duration=60)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"✗ Test failed: {e}")
    finally:
        tester.disconnect()


if __name__ == "__main__":
    main()

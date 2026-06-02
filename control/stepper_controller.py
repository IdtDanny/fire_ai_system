import serial
import serial.tools.list_ports
import time
import logging
from config import CONFIG

class StepperController:
    """
    Serial communication interface to Arduino Nano for stepper motor control.
    Integrates with fire detection system.
    """
    def __init__(self, port=None, baudrate=9600, timeout=2):
        self.serial_conn = None
        self.baudrate = baudrate
        self.timeout = timeout
        self.port = port or self._find_arduino_port()

        if self.port is None:
            logging.error("Arduino not found. Stepper controller unavailable.")
            self.available = False
            return

        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)  # Wait for Arduino reset
            self.available = True
            logging.info(f"Connected to Arduino on {self.port}")
        except Exception as e:
            logging.error(f"Failed to connect to Arduino: {e}")
            self.available = False

    def _find_arduino_port(self):
        """Auto-detect Arduino Nano serial port."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "Arduino" in port.description or "USB-SERIAL" in port.description:
                return port.device
        return None

    def send_command(self, command, wait_response=True):
        """Send a command to Arduino and optionally wait for response."""
        if not self.available or self.serial_conn is None:
            logging.warning("Stepper controller not available")
            return None

        try:
            self.serial_conn.write(f"{command}\n".encode())
            if wait_response:
                response = self.serial_conn.readline().decode().strip()
                logging.info(f"Arduino response: {response}")
                return response
            return None
        except Exception as e:
            logging.error(f"Serial communication error: {e}")
            return None

    def activate(self):
        """Extend mechanism to press fire extinguisher."""
        logging.critical("Sending ACTIVATE command to Arduino")
        return self.send_command("ACTIVATE")

    def reset(self):
        """Retract mechanism to home position."""
        logging.info("Sending RESET command to Arduino")
        return self.send_command("RESET")

    def stop(self):
        """Emergency stop motor."""
        logging.warning("Sending STOP command to Arduino")
        return self.send_command("STOP")

    def get_status(self):
        """Retrieve current mechanism status."""
        response = self.send_command("STATUS")
        if response:
            # Parse response format: "activated=True,emergency=False,extend_limit=False,retract_limit=True"
            status = {}
            for pair in response.split(','):
                if '=' in pair:
                    key, val = pair.split('=')
                    status[key] = val.lower() == 'true'
            return status
        return None

    def close(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("Serial connection closed")
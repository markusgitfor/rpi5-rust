import obd
import threading
import time
import csv
import os
import logging
from datetime import datetime
from typing import Optional, Any
from obd import Unit, OBDCommand
from obd.utils import bytes_to_int


# --- 1. DEFINE THE CUSTOM DECODER ---
def decode_mazda_oil(messages):
    """
    Decodes Mazda SkyActiv Oil Temp from Mode 22 PID 1310.
    Formula: (A * 256 + B) / 100 - 40
    """
    if not messages:
        return None

    # Get the raw data bytes
    d = messages[0].data

    # FIX 1: Ensure we actually have 2 bytes before doing 2-byte math.
    # If we only have 1 byte, 'bytes_to_int' gives a tiny number,
    # resulting in a temp of -39.9 C.
    if len(d) >= 2:
        val = (bytes_to_int(d) / 100.0) - 40.0
        return val * obd.ureg.celsius
    return None


# --- REGISTER MAZDA OIL TEMP ---
mazda_oil_cmd = OBDCommand(
    "MAZDA_OIL_TEMP",          # 1. Name
    "Mazda SkyActiv Oil Temp", # 2. Desc (Not 'description')
    b"221310",                 # 3. Command (Mode 22 + PID 1310 combined)
    2,                         # 4. Bytes (Expected return size)
    decode_mazda_oil,          # 5. Decoder Function
)

obd.commands.MAZDA_OIL_TEMP = mazda_oil_cmd


# --- 1. DEFINE THE OIL PRESSURE DECODER ---
def decode_mazda_oil_pressure(messages):
    """
    Decodes Mazda SkyActiv Oil Pressure from Mode 22 PID 14B3.
    Returns value in kPa.
    """
    if not messages:
        return None

    # Get raw bytes (usually 2 bytes)
    d = messages[0].data

    if len(d) >= 2:
        # The raw value is usually in kPa directly for this PID,
        # or sometimes requires a simple multiplier (e.g., * 1.0)
        val = bytes_to_int(d)

        # Convert to PSI if preferred: val * 0.145038
        return val * obd.ureg.kilopascal  # or just return float 'val'
    return None


# --- REGISTER MAZDA OIL PRESSURE ---
mazda_oil_press_cmd = OBDCommand(
    "MAZDA_OIL_PRESS",
    "Mazda SkyActiv Oil Pressure",
    b"2214B3",                 # Mode 22 + PID 14B3
    2,
    decode_mazda_oil_pressure
)

obd.commands.MAZDA_OIL_PRESS = mazda_oil_press_cmd

# Set the header to the Engine Control Module (ECM/PCM) standard ID 7E0
# TX: 7E0, RX: 7E8
# TODO: enable these if still does not work!
# obd.commands.MAZDA_OIL_TEMP.header = b"7E0"
# obd.commands.MAZDA_OIL_PRESS.header = b"7E0"


class CarLogger:
    def __init__(self, port: str, output_dir: str, obd_enabled: bool) -> None:
        # 1. SETUP DEBUG LOGGING
        # This will create 'debug.log' in the same folder as your CSV
        log_file = os.path.join(output_dir, 'debug.log')
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'  # 'w' overwrites log each time. Use 'a' to append.
        )

        # Also print to console (stdout) for testing when not in car
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)

        self.port: str = port
        self.output_dir: str = output_dir
        self.filename: str = os.path.join(output_dir, 'telemetry.csv')
        self.running: bool = False

        self.connection: Optional[obd.OBD] = None
        self.thread: Optional[threading.Thread] = None
        self.OBD_ENABLED: bool = obd_enabled

        self.commands_to_watch: dict[str, Any] = {
            'RPM': obd.commands.RPM,
            'Speed': obd.commands.SPEED,

            # --- TEMPERATURES ---
            'Coolant': obd.commands.COOLANT_TEMP,
            'Intake Temp': obd.commands.INTAKE_TEMP,
            'Oil Temp': obd.commands.MAZDA_OIL_TEMP,  # Custom PID we made
            'Oil Pres': obd.commands.MAZDA_OIL_PRESS,

            # FUEL TRIMS (The "Correction" Factors)
            'STFT': obd.commands.SHORT_FUEL_TRIM_1,  # Instant correction
            'LTFT': obd.commands.LONG_FUEL_TRIM_1,  # Learned correction over time

            # --- SKYACTIV-X PERFORMANCE ---
            'Load': obd.commands.ENGINE_LOAD,  # Percentage of engine power being used
            # Shows wrong values for now!!!
            # 'Lambda': obd.commands.COMMANDED_EQUIV_RATIO,  # Lean/Rich monitor
            'Timing': obd.commands.TIMING_ADVANCE,  # Ignition timing

            # --- PRESSURE ---
            'Rail Press': obd.commands.FUEL_RAIL_PRESSURE_DIRECT,  # PID 59
        }

    def connect(self) -> bool:
        if not self.OBD_ENABLED:
            logging.info("OBD Disabled in config.")
            return False

        logging.info(f"Attempting connection to {self.port}...")

        try:
            # 2. CONNECTION ATTEMPT
            # We explicitly set protocol to None (Auto) but you can try "6" (ISO 15765-4 CAN 11/500)
            # if auto-negotiation fails frequently with the Carly.
            self.connection = obd.OBD(self.port, fast=False, timeout=30)

            # Add support for custom PID
            self.connection.supported_commands.add(obd.commands.MAZDA_OIL_TEMP)
            self.connection.supported_commands.add(obd.commands.MAZDA_OIL_PRESS)

            if self.connection.is_connected():
                logging.info(f"Connected successfully! Protocol: {self.connection.protocol_name()}")
                logging.info(f"Saving telemetry to: {self.filename}")
                return True
            else:
                logging.error("Connection failed. Status is 'Not Connected'.")
                # Log the internal status to see WHY (e.g., 'ELM327 Gone')
                logging.error(f"OBD Status: {self.connection.status()}")
                return False
        except Exception:
            logging.exception("Crash during connection attempt:")
            return False

    def start_logging(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._log_loop, daemon=True)
        self.thread.start()

    def stop_logging(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.connection:
            self.connection.close()
        logging.info("Logger stopped.")

    def _log_loop(self) -> None:
        logging.info("Starting logging loop...")
        try:
            with open(self.filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                headers: list[str] = ['Timestamp'] + list(self.commands_to_watch.keys())
                writer.writerow(headers)

                while self.running:
                    current_time: str = datetime.now().strftime("%H:%M:%S")
                    row_data: list[Any] = [current_time]

                    if self.connection and self.connection.is_connected():
                        for name, cmd in self.commands_to_watch.items():
                            # FIX 1: Removed 'if self.connection.supports(cmd)' check
                            # We force the query because custom PIDs (Mode 22) are rarely 'supported' in the scan.

                            try:
                                response = self.connection.query(cmd)

                                if not response.is_null():
                                    if hasattr(response.value, 'magnitude'):
                                        # Rounding makes the CSV much cleaner (e.g., 90.0 instead of 90.00000001)
                                        row_data.append(round(response.value.magnitude, 2))
                                    else:
                                        row_data.append(response.value)
                                else:
                                    row_data.append("")  # No data returned
                            except Exception as e:
                                logging.debug(f"Error querying {name}: {e}")
                                row_data.append("ERR")
                    else:
                        logging.warning("OBD disconnected mid-drive!")
                        # If disconnected, fill the row with empty strings to keep CSV structure valid
                        row_data.extend(["DISCONNECTED"] * len(self.commands_to_watch))

                        # Optional: simple reconnect logic
                        # time.sleep(5)
                        # self.connect()

                    writer.writerow(row_data)
                    file.flush()

                    time.sleep(0.5)
        except Exception:
            logging.exception("Logging thread crashed:")

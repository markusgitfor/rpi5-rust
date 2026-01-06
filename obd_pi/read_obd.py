import obd
import threading
import time
import csv
import os
import logging
from datetime import datetime
from typing import Optional, Any


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
            'Coolant': obd.commands.COOLANT_TEMP,
            'Speed': obd.commands.SPEED,
            'RPM': obd.commands.RPM,  # Added RPM as it's a good connection test
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

            if self.connection.is_connected():
                logging.info(f"Connected successfully! Protocol: {self.connection.protocol_name()}")
                logging.info(f"Saving telemetry to: {self.filename}")
                return True
            else:
                logging.error("Connection failed. Status is 'Not Connected'.")
                # Log the internal status to see WHY (e.g., 'ELM327 Gone')
                logging.error(f"OBD Status: {self.connection.status()}")
                return False
        except Exception as e:
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
            # Check if file exists to avoid overwriting headers if restarting?
            # For now, we assume 'w' (overwrite) per your original code
            with open(self.filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                headers: list[str] = ['Timestamp'] + list(self.commands_to_watch.keys())
                writer.writerow(headers)

                while self.running:
                    current_time: str = datetime.now().strftime("%H:%M:%S")
                    row_data: list[Any] = [current_time]

                    if self.connection and self.connection.is_connected():
                        for name, cmd in self.commands_to_watch.items():
                            if self.connection.supports(cmd):
                                response = self.connection.query(cmd)
                                if not response.is_null():
                                    # 3. SAFER DATA EXTRACTION
                                    # Sometimes response.value is not a Quantity (has no magnitude)
                                    if hasattr(response.value, 'magnitude'):
                                        row_data.append(response.value.magnitude)
                                    else:
                                        row_data.append(response.value)
                                else:
                                    row_data.append("")
                            else:
                                row_data.append("N/A")
                    else:
                        logging.warning("OBD disconnected mid-drive!")
                        row_data.append("DISCONNECTED")
                        # Optional: Add logic here to try self.connect() again?

                    writer.writerow(row_data)
                    file.flush()
                    time.sleep(1.0)
        except Exception as e:
            logging.exception("Logging thread crashed:")

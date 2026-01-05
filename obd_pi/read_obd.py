import obd
import threading
import time
import csv
import os
from datetime import datetime
from typing import Optional, Any


class CarLogger:
    def __init__(self, port: str, output_dir: str, obd_enabled: bool) -> None:
        self.port: str = port
        self.output_dir: str = output_dir
        self.filename: str = os.path.join(output_dir, 'telemetry.csv')
        self.running: bool = False

        # 'obd.OBD' is the class from the library
        self.connection: Optional[obd.OBD] = None
        self.thread: Optional[threading.Thread] = None
        self.OBD_ENABLED: bool = obd_enabled

        # Dictionary mapping a name (str) to an OBD command object
        self.commands_to_watch: dict[str, Any] = {
            'Coolant': obd.commands.COOLANT_TEMP,
            'Speed': obd.commands.SPEED,
        }

    def connect(self) -> bool:
        """Attempts to connect to the car. Returns True if successful."""
        if not self.OBD_ENABLED:
            print("[OBD] Disabled in config.")
            return False

        print(f"[OBD] Connecting to adapter on {self.port}...")
        try:
            # There is a service used for bluetooth:
            # sudo nano /etc/systemd/system/carly-bridge.service
            # sudo systemctl status carly-bridge.service
            # Port for the Carly is: CC:03:7B:AE:B0:0E
            self.connection = obd.OBD(self.port, fast=False, timeout=30)

            if self.connection.is_connected():
                print(f"[OBD] Connected! Saving data to: {self.filename}")
                return True
            else:
                print("[OBD] Connection failed (Ignition off?). Telemetry will be skipped.")
                return False
        except Exception as e:
            print(f"[OBD] Error connecting: {e}")
            return False

    def start_logging(self) -> None:
        """Starts the logging thread."""
        self.running = True
        self.thread = threading.Thread(target=self._log_loop, daemon=True)
        self.thread.start()

    def stop_logging(self) -> None:
        """Stops the logging thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.connection:
            self.connection.close()
        print("[OBD] Logger stopped.")

    def _log_loop(self) -> None:
        """The internal loop running in the thread."""
        try:
            with open(self.filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                # Write Header
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
                                    row_data.append(response.value.magnitude)
                                else:
                                    row_data.append("")
                            else:
                                row_data.append("N/A")
                    else:
                        # If connection drops mid-drive, log disconnect
                        row_data.append("DISCONNECTED")

                    writer.writerow(row_data)
                    file.flush()  # Ensure data writes even if power cuts
                    time.sleep(1.0)  # 1Hz sample rate
        except Exception as e:
            print(f"[OBD] Logging thread crashed: {e}")

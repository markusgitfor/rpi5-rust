use chrono::Local;
use log::{error, info};
use std::io::{Read, Write};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::{self, JoinHandle};
use std::time::Duration;

pub struct CarLogger {
    port: String,
    output_dir: String,
    obd_enabled: bool,
    running: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}

impl CarLogger {
    pub fn new(port: String, output_dir: String, obd_enabled: bool) -> Self {
        Self {
            port,
            output_dir,
            obd_enabled,
            running: Arc::new(AtomicBool::new(false)),
            thread: None,
        }
    }

    pub fn connect(&self) -> bool {
        if !self.obd_enabled {
            info!("OBD Disabled in config.");
            return false;
        }

        info!("Attempting connection to {}...", self.port);
        match serialport::new(&self.port, 38400)
            .timeout(Duration::from_millis(500))
            .open()
        {
            Ok(mut port) => {
                let init_cmds = ["AT Z\r", "AT E0\r", "AT L0\r", "AT S0\r", "AT SP 0\r"];
                for cmd in init_cmds.iter() {
                    let _ = port.write_all(cmd.as_bytes());
                    thread::sleep(Duration::from_millis(100));
                    let mut buf = [0; 256];
                    let _ = port.read(&mut buf);
                }
                info!("Connected successfully!");
                true
            }
            Err(e) => {
                error!("Connection failed: {:?}", e);
                false
            }
        }
    }

    #[allow(clippy::collapsible_if)]
    pub fn start_logging(&mut self) {
        self.running.store(true, Ordering::SeqCst);
        let port_name = self.port.clone();
        let output_dir = self.output_dir.clone();
        let running = Arc::clone(&self.running);

        self.thread = Some(thread::spawn(move || {
            let filename = format!("{}/telemetry.csv", output_dir);
            let file = std::fs::File::create(&filename).unwrap();
            let mut writer = csv::Writer::from_writer(file);

            let headers = [
                "Timestamp",
                "RPM",
                "Speed",
                "Coolant",
                "Intake Temp",
                "Oil Temp",
                "Load",
                "Timing",
                "Rail Press",
            ];
            let _ = writer.write_record(headers);

            let mut port = match serialport::new(&port_name, 38400)
                .timeout(Duration::from_millis(500))
                .open()
            {
                Ok(p) => p,
                Err(_) => return,
            };

            while running.load(Ordering::SeqCst) {
                let timestamp = Local::now().format("%Y-%m-%dT%H:%M:%S%.3f").to_string();

                let mut row = vec![timestamp];

                let queries = [
                    ("010C", "RPM"),
                    ("010D", "Speed"),
                    ("0105", "Coolant"),
                    ("010F", "Intake Temp"),
                    ("221310", "Oil Temp"),
                    ("0104", "Load"),
                    ("010E", "Timing"),
                    ("0159", "Rail Press"),
                ];

                for (cmd, _name) in queries.iter() {
                    let full_cmd = format!("{}\r", cmd);
                    if port.write_all(full_cmd.as_bytes()).is_ok() {
                        let mut resp = String::new();
                        let mut buf = [0; 1];
                        let start = std::time::Instant::now();
                        while start.elapsed() < Duration::from_millis(300) {
                            if let Ok(n) = port.read(&mut buf) {
                                if n > 0 {
                                    let c = buf[0] as char;
                                    resp.push(c);
                                    if c == '>' {
                                        break;
                                    }
                                }
                            }
                        }

                        let clean_resp = resp
                            .replace(">", "")
                            .replace(" ", "")
                            .replace("\r", "")
                            .replace("\n", "");
                        let parsed_value = decode_pid(cmd, &clean_resp);
                        row.push(parsed_value);
                    } else {
                        row.push("ERR".to_string());
                    }
                }

                let _ = writer.write_record(&row);
                let _ = writer.flush();
                thread::sleep(Duration::from_millis(500));
            }
        }));
    }

    pub fn stop_logging(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(handle) = self.thread.take() {
            let _ = handle.join();
        }
        info!("Logger stopped.");
    }
}

pub fn decode_pid(cmd: &str, resp: &str) -> String {
    let data = if cmd.starts_with("01") && resp.len() >= 4 {
        let expected_prefix = format!("41{}", &cmd[2..4]);
        if let Some(idx) = resp.find(&expected_prefix) {
            &resp[idx + 4..]
        } else {
            return "".to_string();
        }
    } else if cmd == "221310" && resp.len() >= 6 {
        if let Some(idx) = resp.find("621310") {
            &resp[idx + 6..]
        } else {
            return "".to_string();
        }
    } else {
        return "".to_string();
    };

    let bytes = match hex::decode(data) {
        Ok(b) => b,
        Err(_) => return "ERR".to_string(),
    };

    if bytes.is_empty() {
        return "".to_string();
    }

    match cmd {
        "010C" => {
            if bytes.len() >= 2 {
                let rpm = ((bytes[0] as f32 * 256.0) + bytes[1] as f32) / 4.0;
                format!("{:.2}", rpm)
            } else {
                "".to_string()
            }
        }
        "010D" => {
            format!("{}", bytes[0])
        }
        "0105" | "010F" => {
            format!("{}", bytes[0] as i32 - 40)
        }
        "221310" => {
            if bytes.len() >= 2 {
                let raw_val = (bytes[0] as f32 * 256.0) + bytes[1] as f32;
                let temp_c = (raw_val / 100.0) - 40.0;
                format!("{:.2}", temp_c)
            } else {
                "".to_string()
            }
        }
        "0104" => {
            let load = (bytes[0] as f32 * 100.0) / 255.0;
            format!("{:.2}", load)
        }
        "010E" => {
            let timing = (bytes[0] as f32 / 2.0) - 64.0;
            format!("{:.2}", timing)
        }
        "0159" => {
            if bytes.len() >= 2 {
                let press = ((bytes[0] as f32 * 256.0) + bytes[1] as f32) * 10.0;
                format!("{:.2}", press)
            } else {
                "".to_string()
            }
        }
        _ => "".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_pid_rpm() {
        let resp = "410C 0F A0";
        let result = decode_pid("010C", &resp.replace(" ", ""));
        assert_eq!(result, "1000.00");
    }

    #[test]
    fn test_decode_pid_mazda_oil() {
        let resp = "62 13 10 2E 18";
        let result = decode_pid("221310", &resp.replace(" ", ""));
        assert_eq!(result, "78.00");
    }
}

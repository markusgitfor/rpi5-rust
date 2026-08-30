use chrono::Local;
use log::{error, info};
use serde::Deserialize;
use std::io::{Read, Write};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread::{self, JoinHandle};
use std::time::Duration;

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct ObdCommandConfig {
    #[serde(alias = "label", alias = "description")]
    pub name: String,
    #[serde(alias = "pid", alias = "cmd", alias = "command")]
    pub address: String,
}

pub fn default_obd_commands() -> Vec<ObdCommandConfig> {
    vec![
        ObdCommandConfig {
            name: "RPM".to_string(),
            address: "010C".to_string(),
        },
        ObdCommandConfig {
            name: "Speed".to_string(),
            address: "010D".to_string(),
        },
        ObdCommandConfig {
            name: "Coolant".to_string(),
            address: "0105".to_string(),
        },
        ObdCommandConfig {
            name: "Intake Temp".to_string(),
            address: "010F".to_string(),
        },
        ObdCommandConfig {
            name: "Oil Temp".to_string(),
            address: "221310".to_string(),
        },
        ObdCommandConfig {
            name: "Load".to_string(),
            address: "0104".to_string(),
        },
        ObdCommandConfig {
            name: "Timing".to_string(),
            address: "010E".to_string(),
        },
        ObdCommandConfig {
            name: "Rail Press".to_string(),
            address: "0159".to_string(),
        },
    ]
}

pub struct CarLogger {
    port: String,
    output_dir: String,
    obd_enabled: bool,
    commands: Vec<ObdCommandConfig>,
    running: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}

impl CarLogger {
    pub fn new(
        port: String,
        output_dir: String,
        obd_enabled: bool,
        commands: Option<Vec<ObdCommandConfig>>,
    ) -> Self {
        let commands = commands
            .filter(|c| !c.is_empty())
            .unwrap_or_else(default_obd_commands);
        Self {
            port,
            output_dir,
            obd_enabled,
            commands,
            running: Arc::new(AtomicBool::new(false)),
            thread: None,
        }
    }

    pub fn commands(&self) -> &[ObdCommandConfig] {
        &self.commands
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
        let commands = self.commands.clone();

        self.thread = Some(thread::spawn(move || {
            let filename = format!("{}/telemetry.csv", output_dir);
            let file = std::fs::File::create(&filename).unwrap();
            let mut writer = csv::Writer::from_writer(file);

            let mut headers = vec!["Timestamp".to_string()];
            for cmd in &commands {
                headers.push(cmd.name.clone());
            }
            let _ = writer.write_record(&headers);

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

                for cmd_cfg in commands.iter() {
                    let full_cmd = format!("{}\r", cmd_cfg.address.trim());
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

                        let clean_resp = resp.replace(['>', ' ', '\r', '\n'], "");
                        let parsed_value = decode_pid(&cmd_cfg.address, &clean_resp);
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
    let cmd_clean = cmd.trim().to_ascii_uppercase();
    let resp_clean = resp.trim().to_ascii_uppercase();

    let data = if cmd_clean.starts_with("01") && cmd_clean.len() >= 4 {
        let expected_prefix = format!("41{}", &cmd_clean[2..4]);
        if let Some(idx) = resp_clean.find(&expected_prefix) {
            &resp_clean[idx + 4..]
        } else {
            return "".to_string();
        }
    } else if cmd_clean.starts_with("22") && cmd_clean.len() >= 4 {
        let expected_prefix = format!("62{}", &cmd_clean[2..]);
        if let Some(idx) = resp_clean.find(&expected_prefix) {
            &resp_clean[idx + expected_prefix.len()..]
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

    match cmd_clean.as_str() {
        "010C" => {
            if bytes.len() >= 2 {
                let rpm = ((bytes[0] as f32 * 256.0) + bytes[1] as f32) / 4.0;
                format!("{:.2}", rpm)
            } else {
                "".to_string()
            }
        }
        "010D" => format!("{}", bytes[0]),
        "0105" | "010F" => format!("{}", bytes[0] as i32 - 40),
        "221310" => {
            if bytes.len() >= 2 {
                let raw_val = (bytes[0] as f32 * 256.0) + bytes[1] as f32;
                let temp_c = (raw_val / 100.0) - 40.0;
                format!("{:.2}", temp_c)
            } else {
                "".to_string()
            }
        }
        "2214B3" => {
            if bytes.len() >= 2 {
                let press = (bytes[0] as f32 * 256.0) + bytes[1] as f32;
                format!("{:.2}", press)
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
        _ => {
            if bytes.len() == 1 {
                format!("{}", bytes[0])
            } else if bytes.len() == 2 {
                let val = (bytes[0] as f32 * 256.0) + bytes[1] as f32;
                format!("{:.2}", val)
            } else {
                hex::encode(&bytes)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_pid_rpm() {
        let resp = "410C 0F A0";
        let result = decode_pid("010C", &resp.replace(' ', ""));
        assert_eq!(result, "1000.00");
    }

    #[test]
    fn test_decode_pid_speed() {
        let resp = "410D 3C";
        let result = decode_pid("010D", &resp.replace(' ', ""));
        assert_eq!(result, "60");
    }

    #[test]
    fn test_decode_pid_coolant() {
        let resp = "4105 7B";
        let result = decode_pid("0105", &resp.replace(' ', ""));
        assert_eq!(result, "83");
    }

    #[test]
    fn test_decode_pid_intake_temp() {
        let resp = "410F 3C";
        let result = decode_pid("010F", &resp.replace(' ', ""));
        assert_eq!(result, "20");
    }

    #[test]
    fn test_decode_pid_mazda_oil() {
        let resp = "62 13 10 2E 18";
        let result = decode_pid("221310", &resp.replace(' ', ""));
        assert_eq!(result, "78.00");
    }

    #[test]
    fn test_decode_pid_mazda_oil_pressure() {
        let resp = "62 14 B3 01 2C";
        let result = decode_pid("2214B3", &resp.replace(' ', ""));
        assert_eq!(result, "300.00");
    }

    #[test]
    fn test_decode_pid_load() {
        let resp = "4104 80";
        let result = decode_pid("0104", &resp.replace(' ', ""));
        assert_eq!(result, "50.20");
    }

    #[test]
    fn test_decode_pid_timing() {
        let resp = "410E 80";
        let result = decode_pid("010E", &resp.replace(' ', ""));
        assert_eq!(result, "0.00");
    }

    #[test]
    fn test_decode_pid_rail_pressure() {
        let resp = "4159 01 F4";
        let result = decode_pid("0159", &resp.replace(' ', ""));
        assert_eq!(result, "5000.00");
    }

    #[test]
    fn test_decode_pid_case_insensitive() {
        let resp = "410c 0f a0";
        let result = decode_pid("010c", &resp.replace(' ', ""));
        assert_eq!(result, "1000.00");
    }

    #[test]
    fn test_decode_pid_generic_single_byte() {
        let resp = "412F 64";
        let result = decode_pid("012F", &resp.replace(' ', ""));
        assert_eq!(result, "100");
    }

    #[test]
    fn test_decode_pid_generic_multi_byte() {
        let resp = "4100 00 00 00 00";
        let result = decode_pid("0100", &resp.replace(' ', ""));
        assert_eq!(result, "00000000");
    }

    #[test]
    fn test_decode_pid_errors_and_empty() {
        assert_eq!(decode_pid("010C", "NO DATA"), "");
        assert_eq!(decode_pid("010C", "410C"), "");
        assert_eq!(decode_pid("010C", "410C ZZ"), "ERR");
    }

    #[test]
    fn test_car_logger_custom_and_default_commands() {
        let custom_cmds = vec![
            ObdCommandConfig {
                name: "Battery Voltage".into(),
                address: "0142".into(),
            },
            ObdCommandConfig {
                name: "Fuel Level".into(),
                address: "012F".into(),
            },
        ];

        let logger_custom = CarLogger::new(
            "/dev/rfcomm0".into(),
            "/tmp/test".into(),
            true,
            Some(custom_cmds.clone()),
        );
        assert_eq!(logger_custom.commands(), &custom_cmds);

        let logger_default = CarLogger::new("/dev/rfcomm0".into(), "/tmp/test".into(), true, None);
        assert_eq!(logger_default.commands(), &default_obd_commands());

        let logger_empty = CarLogger::new(
            "/dev/rfcomm0".into(),
            "/tmp/test".into(),
            true,
            Some(vec![]),
        );
        assert_eq!(logger_empty.commands(), &default_obd_commands());
    }
}

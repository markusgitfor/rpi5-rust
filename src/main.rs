use chrono::Local;
use log::{error, info};
use serde::Deserialize;
use std::fs;
use std::thread;
use std::time::Duration;

pub mod camera;
pub mod obd_pi;
pub mod storage;

use camera::CameraRecorder;
use obd_pi::{CarLogger, ObdCommandConfig};
use storage::RingBufferManager;

#[derive(Deserialize)]
struct StorageConfig {
    clip_dir: String,
    max_storage_gigabytes: u64,
}

#[derive(Deserialize)]
struct ObdConfig {
    port: Option<String>,
    enabled: Option<bool>,
    #[serde(default, alias = "pids", alias = "data", alias = "queries")]
    commands: Option<Vec<ObdCommandConfig>>,
}

#[derive(Deserialize)]
struct RecordingConfig {
    segment_seconds: u32,
}

#[derive(Deserialize)]
struct CameraConfig {
    width: u32,
    height: u32,
    fps: u32,
    buffer_count: u32,
    codec: String,
    hdr: String,
    preview: bool,
    extra_args: Vec<String>,
    libav_opts: Option<Vec<String>>,
}

#[derive(Deserialize)]
struct RingBufferConfig {
    check_interval_seconds: u64,
}

#[derive(Deserialize)]
struct Config {
    storage: StorageConfig,
    obd: Option<ObdConfig>,
    recording: RecordingConfig,
    camera: CameraConfig,
    ring_buffer: RingBufferConfig,
}

fn ring_buffer_loop(manager: RingBufferManager, check_interval: u64) {
    loop {
        manager.enforce_limit();
        thread::sleep(Duration::from_secs(check_interval));
    }
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config_str = match fs::read_to_string("config/config.yaml") {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to read config/config.yaml: {}", e);
            std::process::exit(1);
        }
    };

    let config: Config = match serde_yaml::from_str(&config_str) {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to parse config.yaml: {}", e);
            std::process::exit(1);
        }
    };

    let session_time = Local::now().format("%Y%m%d_%H%M%S").to_string();
    let clip_dir = format!("{}/{}", config.storage.clip_dir, session_time);
    fs::create_dir_all(&clip_dir).expect("Failed to create clip directory");

    info!("--- Starting Dashcam Session: {} ---", clip_dir);

    let ring_buffer = RingBufferManager::new(
        config.storage.clip_dir.clone(),
        config.storage.max_storage_gigabytes,
        vec![clip_dir.clone()],
    );

    let mut recorder = CameraRecorder::new(
        clip_dir.clone(),
        config.camera.width,
        config.camera.height,
        config.camera.fps,
        config.camera.buffer_count,
        config.recording.segment_seconds,
        config.camera.codec.clone(),
        config.camera.hdr.clone(),
        config.camera.preview,
        config.camera.extra_args.clone(),
        config.camera.libav_opts.clone(),
    );

    let check_interval = config.ring_buffer.check_interval_seconds;
    thread::spawn(move || {
        ring_buffer_loop(ring_buffer, check_interval);
    });

    let obd_port = config
        .obd
        .as_ref()
        .and_then(|o| o.port.clone())
        .unwrap_or_else(|| "/dev/rfcomm0".to_string());
    let obd_enabled = config.obd.as_ref().and_then(|o| o.enabled).unwrap_or(false);
    let obd_commands = config.obd.as_ref().and_then(|o| o.commands.clone());

    let mut car_logger = CarLogger::new(obd_port, clip_dir.clone(), obd_enabled, obd_commands);

    thread::spawn(move || {
        thread::sleep(Duration::from_secs(11));
        if car_logger.connect() {
            car_logger.start_logging();
            // Let it run forever in this thread until app stops (threads are killed when main dies)
            loop {
                thread::sleep(Duration::from_secs(10));
            }
        }
    });

    // We can handle Ctrl-C using a channel or just let it exit. The python code caught KeyboardInterrupt.
    // In Rust we can use ctrlc crate or just let it die.
    // To gracefully shutdown:

    let (_tx, rx) = std::sync::mpsc::channel::<()>();

    thread::spawn(move || {
        recorder.start();
        loop {
            thread::sleep(Duration::from_secs(2));
            if !recorder.is_running() {
                info!("[MAIN] Recorder pipeline crashed/stopped. Restarting...");
                recorder.stop();
                recorder.start();
                info!("[MAIN] Restart successful.");
            }
            if rx.try_recv().is_ok() {
                recorder.stop();
                break;
            }
        }
    });

    // Wait for Ctrl-C? Rust doesn't do that naturally without a signal handler, but it will kill the process on SIGINT.
    // If we want graceful shutdown on SIGINT, we should catch it.
    // Let's just loop and block main, the process will die on Ctrl-C.
    loop {
        thread::sleep(Duration::from_secs(100));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_config_with_custom_obd_commands() {
        let yaml = r#"
storage:
  clip_dir: "videos"
  max_storage_gigabytes: 12

obd:
  port: "/dev/rfcomm0"
  enabled: true
  commands:
    - name: "Coolant Temp"
      address: "0105"
    - name: "Custom Sensor"
      address: "2214B3"

recording:
  segment_seconds: 60

camera:
  width: 2304
  height: 1008
  fps: 25
  buffer_count: 30
  codec: "libav"
  hdr: "off"
  preview: false
  extra_args: []

ring_buffer:
  check_interval_seconds: 60
"#;

        let config: Config = serde_yaml::from_str(yaml).expect("Failed to parse YAML");
        let obd = config.obd.expect("OBD config missing");
        assert_eq!(obd.port.as_deref(), Some("/dev/rfcomm0"));
        assert_eq!(obd.enabled, Some(true));
        let commands = obd.commands.expect("Commands missing");
        assert_eq!(commands.len(), 2);
        assert_eq!(commands[0].name, "Coolant Temp");
        assert_eq!(commands[0].address, "0105");
        assert_eq!(commands[1].name, "Custom Sensor");
        assert_eq!(commands[1].address, "2214B3");
    }

    #[test]
    fn test_deserialize_config_with_pids_alias() {
        let yaml = r#"
storage:
  clip_dir: "videos"
  max_storage_gigabytes: 12

obd:
  port: "/tmp/ttyCarly"
  enabled: true
  pids:
    - label: "Engine RPM"
      pid: "010C"

recording:
  segment_seconds: 60

camera:
  width: 2304
  height: 1008
  fps: 25
  buffer_count: 30
  codec: "libav"
  hdr: "off"
  preview: false
  extra_args: []

ring_buffer:
  check_interval_seconds: 60
"#;

        let config: Config = serde_yaml::from_str(yaml).expect("Failed to parse YAML");
        let obd = config.obd.expect("OBD config missing");
        let commands = obd.commands.expect("Commands missing");
        assert_eq!(commands.len(), 1);
        assert_eq!(commands[0].name, "Engine RPM");
        assert_eq!(commands[0].address, "010C");
    }
}

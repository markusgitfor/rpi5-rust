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
    baudrate: Option<u32>,
    startup_delay_seconds: Option<u64>,
    query_interval_ms: Option<u64>,
    timeout_ms: Option<u64>,
    init_commands: Option<Vec<String>>,
    #[serde(default, alias = "pids", alias = "data", alias = "queries")]
    commands: Option<Vec<ObdCommandConfig>>,
}

#[derive(Deserialize)]
struct RecordingConfig {
    segment_seconds: u32,
    restart_check_interval_seconds: Option<u64>,
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
    autofocus_mode: Option<String>,
    lens_position: Option<f32>,
    denoise: Option<String>,
    exposure: Option<String>,
    awb: Option<String>,
    roi: Option<String>,
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
        config.camera.autofocus_mode.clone(),
        config.camera.lens_position,
        config.camera.denoise.clone(),
        config.camera.exposure.clone(),
        config.camera.awb.clone(),
        config.camera.roi.clone(),
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
    let obd_baudrate = config.obd.as_ref().and_then(|o| o.baudrate);
    let obd_startup_delay = config
        .obd
        .as_ref()
        .and_then(|o| o.startup_delay_seconds)
        .unwrap_or(11);
    let obd_query_interval = config.obd.as_ref().and_then(|o| o.query_interval_ms);
    let obd_timeout = config.obd.as_ref().and_then(|o| o.timeout_ms);
    let obd_init_cmds = config.obd.as_ref().and_then(|o| o.init_commands.clone());
    let obd_commands = config.obd.as_ref().and_then(|o| o.commands.clone());

    let mut car_logger = CarLogger::new(
        obd_port,
        clip_dir.clone(),
        obd_enabled,
        obd_baudrate,
        obd_query_interval,
        obd_timeout,
        obd_init_cmds,
        obd_commands,
    );

    thread::spawn(move || {
        if obd_startup_delay > 0 {
            thread::sleep(Duration::from_secs(obd_startup_delay));
        }
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

    let restart_interval = config.recording.restart_check_interval_seconds.unwrap_or(2);

    thread::spawn(move || {
        recorder.start();
        loop {
            thread::sleep(Duration::from_secs(restart_interval));
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
    fn test_deserialize_config_full() {
        let yaml = r#"
storage:
  clip_dir: "videos"
  max_storage_gigabytes: 12

obd:
  port: "/dev/rfcomm0"
  enabled: true
  baudrate: 115200
  startup_delay_seconds: 5
  query_interval_ms: 250
  timeout_ms: 300
  init_commands:
    - "AT Z"
    - "AT SP 0"
  commands:
    - name: "Coolant Temp"
      address: "0105"
    - name: "Custom Sensor"
      address: "2214B3"

recording:
  segment_seconds: 60
  restart_check_interval_seconds: 3

camera:
  width: 2304
  height: 1008
  fps: 25
  buffer_count: 30
  codec: "libav"
  hdr: "off"
  preview: false
  autofocus_mode: "manual"
  lens_position: 0.2
  denoise: "cdn_off"
  exposure: "short"
  awb: "auto"
  roi: "0.0,0.0,1.0,0.77777"
  extra_args: ["--nopreview"]

ring_buffer:
  check_interval_seconds: 60
"#;

        let config: Config = serde_yaml::from_str(yaml).expect("Failed to parse YAML");
        let obd = config.obd.expect("OBD config missing");
        assert_eq!(obd.port.as_deref(), Some("/dev/rfcomm0"));
        assert_eq!(obd.enabled, Some(true));
        assert_eq!(obd.baudrate, Some(115200));
        assert_eq!(obd.startup_delay_seconds, Some(5));
        assert_eq!(obd.query_interval_ms, Some(250));
        assert_eq!(obd.timeout_ms, Some(300));
        assert_eq!(
            obd.init_commands.as_ref().unwrap(),
            &vec!["AT Z".to_string(), "AT SP 0".to_string()]
        );
        let commands = obd.commands.expect("Commands missing");
        assert_eq!(commands.len(), 2);
        assert_eq!(commands[0].name, "Coolant Temp");
        assert_eq!(commands[0].address, "0105");
        assert_eq!(commands[1].name, "Custom Sensor");
        assert_eq!(commands[1].address, "2214B3");

        assert_eq!(config.recording.restart_check_interval_seconds, Some(3));
        assert_eq!(config.camera.autofocus_mode.as_deref(), Some("manual"));
        assert_eq!(config.camera.lens_position, Some(0.2));
        assert_eq!(config.camera.denoise.as_deref(), Some("cdn_off"));
        assert_eq!(config.camera.exposure.as_deref(), Some("short"));
        assert_eq!(config.camera.awb.as_deref(), Some("auto"));
        assert_eq!(config.camera.roi.as_deref(), Some("0.0,0.0,1.0,0.77777"));
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

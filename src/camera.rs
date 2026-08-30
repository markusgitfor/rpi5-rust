use log::{error, info, warn};
use std::process::{Child, Command, Stdio};

pub struct CameraRecorder {
    pub output_dir: String,
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub buffer_count: u32,
    pub segment_seconds: u32,
    pub codec: String,
    pub hdr: String,
    pub preview: bool,
    pub extra_args: Vec<String>,
    pub libav_opts: Vec<String>,

    pub rpicam_process: Option<Child>,
    pub ffmpeg_process: Option<Child>,
}

impl CameraRecorder {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        output_dir: String,
        width: u32,
        height: u32,
        fps: u32,
        buffer_count: u32,
        segment_seconds: u32,
        codec: String,
        hdr: String,
        preview: bool,
        extra_args: Vec<String>,
        libav_opts: Option<Vec<String>>,
    ) -> Self {
        std::fs::create_dir_all(&output_dir).ok();
        Self {
            output_dir,
            width,
            height,
            fps,
            buffer_count,
            segment_seconds,
            codec,
            hdr,
            preview,
            extra_args,
            libav_opts: libav_opts.unwrap_or_else(|| {
                vec![
                    "crf=23".into(),
                    "preset=superfast".into(),
                    "profile=high".into(),
                    "maxrate=15M".into(),
                    "bufsize=30M".into(),
                    format!("g={}", fps),
                ]
            }),
            rpicam_process: None,
            ffmpeg_process: None,
        }
    }

    pub fn is_running(&mut self) -> bool {
        let rpicam_alive = match &mut self.rpicam_process {
            Some(child) => matches!(child.try_wait(), Ok(None)),
            None => false,
        };
        let ffmpeg_alive = match &mut self.ffmpeg_process {
            Some(child) => matches!(child.try_wait(), Ok(None)),
            None => false,
        };
        rpicam_alive && ffmpeg_alive
    }

    pub fn start(&mut self) {
        if self.is_running() {
            warn!("Recording is already running.");
            return;
        }

        let mut rpicam_args: Vec<String> = vec![
            "-t".into(),
            "0".into(),
            "--width".into(),
            self.width.to_string(),
            "--height".into(),
            self.height.to_string(),
            "--framerate".into(),
            self.fps.to_string(),
            "--buffer-count".into(),
            self.buffer_count.to_string(),
            "--autofocus-mode".into(),
            "manual".into(),
            "--lens-position".into(),
            "0.2".into(),
            "--denoise".into(),
            "cdn_off".into(),
            "--exposure".into(),
            "short".into(),
            "--awb".into(),
            "auto".into(),
            "--hdr".into(),
            self.hdr.clone(),
            "--roi".into(),
            "0.0,0.0,1.0,0.77777".into(),
            "--codec".into(),
            self.codec.clone(),
            "--inline".into(),
            "-o".into(),
            "-".into(),
        ];

        if !self.preview {
            rpicam_args.push("--nopreview".into());
        }

        if self.codec == "libav" {
            rpicam_args.push("--libav-format".into());
            rpicam_args.push("mpegts".into());
            rpicam_args.push("--libav-video-codec-opts".into());
            rpicam_args.push(self.libav_opts.join(";"));
        }

        rpicam_args.extend(self.extra_args.iter().cloned());

        let output_pattern = format!("{}/%Y%m%d_%H%M%S.mp4", self.output_dir);
        let ffmpeg_args = vec![
            "-y".to_string(),
            "-loglevel".to_string(),
            "error".to_string(),
            "-thread_queue_size".to_string(),
            "8192".to_string(),
            "-f".to_string(),
            "mpegts".to_string(),
            "-i".to_string(),
            "-".to_string(),
            "-c:v".to_string(),
            "copy".to_string(),
            "-an".to_string(),
            "-f".to_string(),
            "segment".to_string(),
            "-segment_time".to_string(),
            self.segment_seconds.to_string(),
            "-reset_timestamps".to_string(),
            "1".to_string(),
            "-strftime".to_string(),
            "1".to_string(),
            "-segment_format".to_string(),
            "mp4".to_string(),
            "-segment_format_options".to_string(),
            "movflags=+faststart".to_string(),
            output_pattern,
        ];

        info!("Starting recording to: {}", self.output_dir);

        let rpicam = Command::new("rpicam-vid")
            .args(&rpicam_args)
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn();

        let mut rpicam = match rpicam {
            Ok(child) => child,
            Err(e) => {
                error!("Failed to start rpicam-vid: {}", e);
                self.stop();
                return;
            }
        };

        let stdout = rpicam.stdout.take().unwrap();

        let ffmpeg = Command::new("ffmpeg")
            .args(&ffmpeg_args)
            .stdin(stdout)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();

        let ffmpeg = match ffmpeg {
            Ok(child) => child,
            Err(e) => {
                error!("Failed to start ffmpeg: {}", e);
                self.stop();
                return;
            }
        };

        self.rpicam_process = Some(rpicam);
        self.ffmpeg_process = Some(ffmpeg);
    }

    pub fn stop(&mut self) {
        info!("Stopping recording...");

        if let Some(mut rpicam) = self.rpicam_process.take() {
            let _ = rpicam.kill();
            let _ = rpicam.wait();
        }

        if let Some(mut ffmpeg) = self.ffmpeg_process.take() {
            #[cfg(unix)]
            {
                unsafe {
                    libc::kill(ffmpeg.id() as libc::pid_t, libc::SIGINT);
                }
            }
            std::thread::sleep(std::time::Duration::from_millis(500));
            let _ = ffmpeg.kill();
            let _ = ffmpeg.wait();
        }

        info!("Recording stopped.");
    }
}

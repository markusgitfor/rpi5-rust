import unittest
from unittest.mock import patch, MagicMock
import os
import time

from camera.recorder import CameraRecorder
from obd_pi.read_obd import CarLogger


class TestDashcamSimulation(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_simulation_videos"
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        # Clean up created files
        csv_file = os.path.join(self.test_dir, "telemetry.csv")
        log_file = os.path.join(self.test_dir, "debug.log")
        if os.path.exists(csv_file):
            os.remove(csv_file)
        if os.path.exists(log_file):
            os.remove(log_file)
        try:
            os.rmdir(self.test_dir)
        except OSError:
            pass

    @patch('subprocess.Popen')
    def test_camera_recorder_simulation(self, mock_popen):
        """Simulate and test that the camera recorder correctly creates and stops processes."""
        # Mock the subprocesses
        mock_rpicam = MagicMock()
        mock_rpicam.poll.return_value = None
        mock_ffmpeg = MagicMock()
        mock_ffmpeg.poll.return_value = None

        # Popen returns mock_rpicam then mock_ffmpeg
        mock_popen.side_effect = [mock_rpicam, mock_ffmpeg]

        recorder = CameraRecorder(output_dir=self.test_dir, segment_seconds=2)
        recorder.start()

        # Assert Popen was called twice (once for rpicam-vid, once for ffmpeg)
        self.assertEqual(mock_popen.call_count, 2)

        # Check that the processes were assigned
        self.assertIsNotNone(recorder.rpicam_process)
        self.assertIsNotNone(recorder.ffmpeg_process)

        # Simulate stopping
        recorder.stop()

        # Check termination of subprocesses
        mock_rpicam.terminate.assert_called_once()
        mock_ffmpeg.send_signal.assert_called_once()

    @patch('obd.OBD')
    def test_obd_bluetooth_simulation(self, mock_obd_class):
        """Simulate and test that the OBD logger correctly connects, queries, and writes telemetry."""
        # Create a mock OBD instance
        mock_obd_instance = MagicMock()
        mock_obd_class.return_value = mock_obd_instance

        mock_obd_instance.is_connected.return_value = True
        mock_obd_instance.protocol_name.return_value = "Mock Protocol"
        mock_obd_instance.status.return_value = "Connected"

        # Mock query responses
        mock_response = MagicMock()
        mock_response.is_null.return_value = False
        mock_response.value.magnitude = 42.0
        mock_obd_instance.query.return_value = mock_response

        logger = CarLogger(port="mock_port", output_dir=self.test_dir, obd_enabled=True)

        # Test connection
        connected = logger.connect()
        self.assertTrue(connected)

        # Test logging loop briefly
        logger.start_logging()
        time.sleep(1.5)  # Let the thread run for a bit to generate some CSV data
        logger.stop_logging()

        # Check that query was called
        self.assertTrue(mock_obd_instance.query.call_count > 0)

        # Verify CSV was created
        csv_file = os.path.join(self.test_dir, "telemetry.csv")
        self.assertTrue(os.path.exists(csv_file))

        # Read the CSV to ensure it has data rows
        with open(csv_file, 'r') as f:
            lines = f.readlines()
            self.assertTrue(len(lines) > 1, "CSV should contain header and at least one data row")


if __name__ == '__main__':
    unittest.main()

from abc import ABC, abstractmethod
import numpy as np


class VideoOperation(ABC):
    """
    Base class for all video post-processing operations.
    """

    @abstractmethod
    def apply(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply operation to a single frame.
        """
        pass

    def setup(self, frame: np.ndarray):
        """
        Optional setup step (called once with first frame).
        """
        pass

    def teardown(self):
        """
        Optional cleanup.
        """
        pass

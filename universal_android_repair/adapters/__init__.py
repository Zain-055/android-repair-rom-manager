"""Platform adapters for supported Android device families."""

from .base import DeviceAdapter, AdapterSupportProfile
from .google_tensor import GoogleTensorAdapter
from .mediatek import MediaTekAdapter
from .qualcomm import QualcommAdapter
from .samsung import SamsungAdapter
from .unisoc import UnisocAdapter

__all__ = [
    "AdapterSupportProfile",
    "DeviceAdapter",
    "GoogleTensorAdapter",
    "MediaTekAdapter",
    "QualcommAdapter",
    "SamsungAdapter",
    "UnisocAdapter",
]

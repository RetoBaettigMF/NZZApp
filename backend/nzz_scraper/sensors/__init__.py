"""Sensor-Schicht: messbare Aussagen über den Browserzustand."""
from .auth import LoginSensor
from .blocking import BlockingSensor
from .consent import ConsentSensor
from .content import ContentQualitySensor
from .page_type import PageTypeSensor
from .paywall import PaywallSensor
from .types import Sensor, SensorResult, Signal, combine, unknown

__all__ = [
    'LoginSensor', 'BlockingSensor', 'ConsentSensor', 'ContentQualitySensor',
    'PageTypeSensor', 'PaywallSensor', 'Sensor', 'SensorResult', 'Signal',
    'combine', 'unknown',
]

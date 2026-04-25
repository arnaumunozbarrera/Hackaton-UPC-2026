"""Registry of offline-trainable AI predictors."""

from __future__ import annotations

from app.prediction.cleaning_interface_ai import train_cleaning_interface_model
from app.prediction.heating_elements_ai import train_heating_elements_model
from app.prediction.insulation_panels_ai import train_insulation_panels_model
from app.prediction.linear_guide_ai import train_linear_guide_model
from app.prediction.nozzle_plate_ai import train_nozzle_plate_model
from app.prediction.recoater_blade_ai import train_recoater_blade_model
from app.prediction.recoater_drive_motor_ai import train_recoater_drive_motor_model
from app.prediction.temperature_sensors_ai import train_temperature_sensors_model
from app.prediction.thermal_firing_resistors_ai import (
    train_thermal_firing_resistors_model,
)


MODEL_FAMILY_BY_COMPONENT = {
    "cleaning_interface": "cleaning_interface_sklearn_gradient_boosting",
    "heating_elements": "heating_elements_sklearn_gradient_boosting",
    "insulation_panels": "insulation_panels_sklearn_gradient_boosting",
    "linear_guide": "linear_guide_sklearn_gradient_boosting",
    "nozzle_plate": "nozzle_plate_sklearn_gradient_boosting",
    "recoater_blade": "recoater_blade_sklearn_gradient_boosting",
    "recoater_drive_motor": "recoater_drive_motor_sklearn_gradient_boosting",
    "temperature_sensors": "temperature_sensors_sklearn_gradient_boosting",
    "thermal_firing_resistors": "thermal_firing_resistors_sklearn_gradient_boosting",
}

TRAINERS_BY_COMPONENT = {
    "cleaning_interface": train_cleaning_interface_model,
    "heating_elements": train_heating_elements_model,
    "insulation_panels": train_insulation_panels_model,
    "linear_guide": train_linear_guide_model,
    "nozzle_plate": train_nozzle_plate_model,
    "recoater_blade": train_recoater_blade_model,
    "recoater_drive_motor": train_recoater_drive_motor_model,
    "temperature_sensors": train_temperature_sensors_model,
    "thermal_firing_resistors": train_thermal_firing_resistors_model,
}

PREDICTION_METHOD = "supervised_synthetic_gradient_boosting"

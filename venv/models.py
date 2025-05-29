from json import loads
from typing import Any
import numpy as np


# declan if ur reading this, why the hell is the model trained in imperial units?
# every time one of these metric to imperial conversion functions ends up on the call stack i hope every one of your toes meets some hardwood furniture at a velocity measured in a 3d vector of floats measured in ft/sec


def c_to_f(c: float) -> float:
        return c * 9/5 + 32


def mm_to_in(mm: float) -> float:
        return mm / 25.4


with open("model-a.json", "r") as file:
        model_a_parameters: dict[Any, Any] = loads(file.read())


def sigmoid(z: Any):
        return 1 / (1 + np.exp(-z))


def model_a(snowfall_mm: float, prev_snow_mm: float, temp_c: float) -> float:
        snowfall_in = mm_to_in(snowfall_mm)
        prev_snow_in = mm_to_in(prev_snow_mm)
        temp_f = c_to_f(temp_c)

        if snowfall_in < 0.2 and prev_snow_in < 0.2:
                return 0.0

        temp_f = max(temp_f, 10)

        initial_vector = np.array((snowfall_in, prev_snow_in, temp_f, 1))
        means_vector = np.array((*model_a_parameters["means"], 0))
        stdevs_vector = np.array((*model_a_parameters["stdevs"], 1))
        adjusted_vector = (initial_vector - means_vector) / stdevs_vector

        fc1_vector = np.array(model_a_parameters["fc1_weights"])
        z1_vector = np.dot(fc1_vector, adjusted_vector)

        swiglu_out_vector = np.append(z1_vector[:25] * sigmoid(z1_vector[25:]), 1.0)
        fc2_vector = np.array(model_a_parameters["fc2_weights"])
        z2_scalar = np.dot(fc2_vector, swiglu_out_vector)

        prediction = sigmoid(z2_scalar)

        if 0.51 <= prediction <= 0.85:
                prediction = 1 - prediction

        return min(prediction, 0.99) 

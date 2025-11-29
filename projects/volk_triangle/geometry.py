"""
Auto-refactor: normalize formatting for geometry.py
"""

#!/usr/bin/env python3

import math
from typing import Tuple

# Bipolar coordinates (eta, rho) to Cartesian (x, y) with scale a
def bipolar_to_cartesian(eta: float, rho: float, a: float) -> Tuple[float, float]:
    den = (math.cosh(eta) - math.cos(rho))
    x = a * math.sinh(eta) / den
    y = a * math.sin(rho) / den
    return x, y

# Cartesian to bipolar (eta, rho) with scale a
def cartesian_to_bipolar(x: float, y: float, a: float) -> Tuple[float, float]:
    # Simple inversion for reference; robust version requires care
    r1 = math.hypot(x - a, y)
    r2 = math.hypot(x + a, y)
    eta = math.log(r1 / r2)
    rho = math.atan2(2*a*y, (x*x + y*y - a*a))
    return eta, rho

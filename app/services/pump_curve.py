from __future__ import annotations

PUMP_MIN_RPM = 800
PUMP_MAX_RPM = 4800
PUMP_PWM_CURVE = [
    (40, 1304),
    (50, 1820),
    (59, 2350),
    (60, 2400),
    (70, 3020),
    (80, 3720),
    (90, 4520),
    (100, 4790),
]


def percent_to_rpm(percent: int, max_rpm: int, min_rpm: int) -> int:
    if percent <= 0:
        return 0
    rpm = int(round(max_rpm * percent / 100))
    return max(min_rpm, rpm)


def pump_pwm_for_rpm(target_rpm: int) -> int | None:
    if target_rpm <= 0:
        return 0
    points = sorted(PUMP_PWM_CURVE, key=lambda item: item[1])
    if not points:
        return None
    if target_rpm <= points[0][1]:
        return points[0][0]
    if target_rpm >= points[-1][1]:
        return points[-1][0]
    for (pwm_low, rpm_low), (pwm_high, rpm_high) in zip(points, points[1:]):
        if rpm_low <= target_rpm <= rpm_high:
            span = rpm_high - rpm_low
            if span <= 0:
                return pwm_low
            ratio = (target_rpm - rpm_low) / span
            pwm = pwm_low + ratio * (pwm_high - pwm_low)
            return int(round(max(0, min(100, pwm))))
    return None


def pump_rpm_for_pwm(pwm_percent: int) -> int | None:
    if pwm_percent <= 0:
        return 0
    points = sorted(PUMP_PWM_CURVE, key=lambda item: item[0])
    if not points:
        return None
    if pwm_percent <= points[0][0]:
        return points[0][1]
    if pwm_percent >= points[-1][0]:
        return points[-1][1]
    for (pwm_low, rpm_low), (pwm_high, rpm_high) in zip(points, points[1:]):
        if pwm_low <= pwm_percent <= pwm_high:
            span = pwm_high - pwm_low
            if span <= 0:
                return rpm_low
            ratio = (pwm_percent - pwm_low) / span
            rpm = rpm_low + ratio * (rpm_high - rpm_low)
            return int(round(rpm))
    return None

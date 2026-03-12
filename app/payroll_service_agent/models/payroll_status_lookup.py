from enum import Enum


class PayrollStatus(str, Enum):
    PAYROLL = "payroll"
    BENEFITS = "benefits"
    TIME_OFF = "time_off"
    GENERAL = "general"

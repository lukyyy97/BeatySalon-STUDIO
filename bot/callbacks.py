"""CallbackData factories (callback_data is limited to 64 bytes, keep fields short)."""
from aiogram.filters.callback_data import CallbackData


class MenuCb(CallbackData, prefix="menu"):
    action: str  # main | book | my | services | contacts


class ServiceCb(CallbackData, prefix="svc"):
    id: int


class MasterCb(CallbackData, prefix="mst"):
    id: int  # 0 = any free master


class DateCb(CallbackData, prefix="dt"):
    value: str  # ISO date, YYYY-MM-DD


class TimeCb(CallbackData, prefix="tm"):
    minute: int  # minutes from midnight (':' is a reserved separator, so no 'HH:MM' here)


class FlowNavCb(CallbackData, prefix="fnav"):
    scope: str  # c = client flow, a = admin flow
    to: str  # step to go back to


class StepCb(CallbackData, prefix="step"):
    action: str  # name_keep | phone_skip


class ConfirmCb(CallbackData, prefix="cf"):
    action: str  # yes | no


class MyApptCb(CallbackData, prefix="ma"):
    action: str  # view | ask | yes
    id: int = 0


class AdmMenuCb(CallbackData, prefix="am"):
    action: str  # main | schedule | sched_date | add | services | masters | timeoff | broadcast


class AdmSchedCb(CallbackData, prefix="as"):
    d: str  # ISO date
    m: int = 0  # master filter, 0 = all


class AdmApptCb(CallbackData, prefix="aa"):
    action: str  # view | ask | yes
    id: int


class AdmCatCb(CallbackData, prefix="ac"):
    action: str
    id: int = 0
    extra: int = 0


class AdmOffCb(CallbackData, prefix="ao"):
    action: str  # list | add | quick | whole | hours | del
    m: int = 0
    id: int = 0
    v: str = ""


class BroadcastCb(CallbackData, prefix="bc"):
    action: str  # send | edit | cancel

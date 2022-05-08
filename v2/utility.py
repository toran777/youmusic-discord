import datetime


def to_string_time(time: int) -> str:
    return str(datetime.timedelta(seconds=time))

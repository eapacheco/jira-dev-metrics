from datetime import datetime


def strptime(date_str):
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")


def datetime_compare(a, b):
    """
    Returns the difference in seconds between two dates.

    Args:
        a: string or datetime object
        b: string or datetime object

    Returns:
        float: Negative seconds if a is before b,
               0 if a is equal to b,
               positive seconds if a is after b
    """
    start = strptime(a) if isinstance(a, str) else a
    end = strptime(b) if isinstance(b, str) else b
    span = end - start
    return -span.total_seconds()

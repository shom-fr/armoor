from woom.util import WoomDate


def filter_woomdate(date: str):
    """Convert a string into a WoomDate object."""
    if date == "today":
        return WoomDate.today()
    else:
        return WoomDate(date)

JINJA_FILTERS = {"woomdate": filter_woomdate}

import itertools as it

class Day:
    """
    Docstring for Day
    1440 min in day, write time in order
    hours*60 + minutes
    """

    WEEK_DAYS = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
        0: "monday",
        1: "tuesday",
        2: "wednesday",
        3: "thursday",
        4: "friday",
        5: "saturday",
        6: "sunday"
    }

    def __init__(self, number, firstDayInMounth = 0):
        self.day_of_the_week = (number - 1) % 7 + firstDayInMounth
        self.events = {}
        self.events[0] = {
            "name": "start of the day",
            "description": "none",
            "end_time": 0
        }
        self.events[1440 - 1] = {
            "name": "start of the day",
            "description": "none",
            "end_time": 1440 - 1
        }

    def add_event(self, start_time, duration_time, name, description):
        if (not any(start_time < i < start_time + duration_time for i in self.events.keys()) or
            start_time in self.events and self.events[start_time] == None):
            self.events[start_time] = {
                "name": name,
                "description": description,
                "end_time": start_time + duration_time
            }
            return True
        return False

    def rm_event(self, start_time):
        if (start_time in self.events):
            self.events[start_time] = None
            return True
        return False

    def get_events(self):
        return self.events

    def __str__(self):
        stringEvents = f"{self.WEEK_DAYS[self.day_of_the_week]}\n"
        skip_items = 2
        for time, event in self.events.items():
            if (skip_items == 0):
                stringEvents += "- " + time_to_str(time) + "-" + time_to_str(event["end_time"]) + "\n- " + event["name"] + "\n=> " + event["description"]+ "\n"
            else:
                skip_items -= 1
        return str(stringEvents)

def time_to_str(time):
    return f"{time//60}:{time%60}"
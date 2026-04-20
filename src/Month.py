from src.Day import *


class Month:
    """
    Max 31 days in month, depends on self month
    """

    DAYS_IN_MONTH = {
        1: 31,
        2: 28,
        3: 31,
        4: 30,
        5: 31,
        6: 30,
        7: 31,
        8: 31,
        9: 30,
        10: 31,
        11: 30,
        12: 31,
    }

    MONTH_NUMBERS = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    def __init__(self, month, firstDay = 0):
        self.first_day = firstDay
        self.month_name: int = month
        self.days: Day = {}

    def add_event(self, dayNumber, eventStartTime, eventDurationTime, eventName, eventDiscription):
        if (not dayNumber in self.days):
            self.days[dayNumber] = Day(dayNumber)
        if (self.days[dayNumber].add_event(eventStartTime, eventDurationTime, eventName, eventDiscription)):
            return True
        return False
    
    def rm_event(self, dayNumber, startTime):
        if (dayNumber in self.days):
            self.days[dayNumber].rm_event(startTime)
            return True
        return False

    def get_month(self):
        return self.days
    
    def __str__(self):
        resultSTR = ""
        for dayNumber, day in self.days.items():
            resultSTR += f"========{dayNumber}========\n{str(day)}"
        return resultSTR


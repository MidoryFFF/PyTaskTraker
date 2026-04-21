import src.Month as Month


class Year:
    def __init__(self, yearNumber, firstDay = 0):
        self.first_day = firstDay
        self.months: Month = {}
        self.isLeapYear = True if yearNumber % 400 == 0 or (not (yearNumber % 100 == 0) and yearNumber % 4 == 0) else False


    def add_event(self, dayNumber, monthNumber, eventStartTime, eventDurationTime, eventName, eventDiscription):
        # create new month
        if (not monthNumber in self.months):
            firstWeekDay = 0
            for i in range(1, monthNumber):
                if (self.isLeapYear):
                    firstWeekDay = (((Month.Month.DAYS_IN_MONTH[i] + 1) if i == 2 else Month.Month.DAYS_IN_MONTH[i]) + firstWeekDay)%7
                else:
                    firstWeekDay = (Month.Month.DAYS_IN_MONTH[i] + firstWeekDay)%7
            self.months[monthNumber] = Month.Month(firstWeekDay)

        # use existing month
        if (self.months[monthNumber].add_event(dayNumber, eventStartTime, eventDurationTime, eventName, eventDiscription)):
            return True
        return False

    def __str__(self):
        resultStr = ""
        for name, month in self.months.items():# add MONTH_NUMBERS for better readability
            resultStr += str(name) + "\n" + str(month)
        return resultStr
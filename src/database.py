import litesql

# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE
# DO THE FUCKING ARCHITECTURE

class Day:
    """
    Docstring for Day
    1440 min in day, write time in order
    hours*60 + minutes
    """
    def __init__(self, number, weekPos):
        self._number = number
        self.day_of_the_week = weekPos % 7
        self.events = {}
    
    def add_event(self, start_time, duration_time, name, description):
        if (any(start_time < i < start_time + duration_time for i in self.events.keys())):
            self.events[start_time] = {
                "name": name,
                "description": description,
                "end_time": start_time + duration_time
            }
    
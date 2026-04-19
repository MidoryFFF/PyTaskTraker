from src.Month import Month


test_month = Month(1)
print(test_month.add_event(1, 7*60 + 30, 60, "Что-то", "что-то будет"))
print(test_month.add_event(1, 9*60 + 30, 60, "Что-то1", "что-то будет1"))
print(test_month.add_event(1, 8*60 + 30, 120, "Что-то2", "что-то будет2"))
print(test_month.add_event(5, 8*60 + 30, 120, "Что-то2", "что-то будет2"))

print(test_month)

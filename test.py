from src.Year import Year


test_year = Year(2026)
print(test_year.add_event(1, 1, 7*60 + 30, 60, "Что-то", "что-то будет"))
print(test_year.add_event(1, 1, 9*60 + 30, 60, "Что-то1", "что-то будет1"))
print(test_year.add_event(1, 1, 8*60 + 30, 120, "Что-то2", "что-то будет2"))
print(test_year.add_event(4, 1, 7*60 + 30, 60, "Что-то3", "что-то будет3"))
print(test_year.add_event(4, 1, 9*60 + 30, 60, "Что-то4", "что-то будет4"))
print(test_year.add_event(10, 1, 8*60 + 30, 120, "Что-то5", "что-то будет5"))
print(test_year.add_event(4, 5, 8*60 + 30, 120, "Что-то6", "что-то будет6"))
print(test_year.add_event(1, 5, 8*60 + 30, 120, "Что-то7", "что-то будет7"))

print(test_year)

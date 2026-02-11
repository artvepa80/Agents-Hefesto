import re

pattern = r"(?i)AIza[0-9A-Za-z\-_]{30,}"
value = "AIzaSyFakeKeyWithMoreThan30CharactersHere123456"

print(f"Pattern: {pattern}")
print(f"Value: {value}")

match = re.search(pattern, value)
print(f"Match: {match}")
if match:
    print("MATCHED!")
else:
    print("NO MATCH")

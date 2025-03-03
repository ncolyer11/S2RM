import re
import json

with open("data/items.txt", "r") as f:
    lines = f.readlines()

pattern = re.compile(r'\.stacksTo\((16|1)\)|ToolMaterial|ArmorMaterial')
limited_stacked_lines = [line for line in lines if pattern.search(line)]

limited_stack_items = {}
for line in limited_stacked_lines:
    material = line.split(" ")[0].lower()
    quantity = 16 if "16" in line else 1
    limited_stack_items[material] = quantity

# Sort the dictionary by key then quantity value
sorted_limited_stack_items = dict(sorted(limited_stack_items.items(), key=lambda x: (x[0], x[1])))

with open("data/116_stacks.json", "w") as f:
    json.dump(sorted_limited_stack_items, f, indent=4)

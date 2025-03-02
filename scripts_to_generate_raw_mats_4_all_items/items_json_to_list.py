import os
import json

# Define the path to the folder
folder_path = './items'

# Dictionary to store file names
items_dict = {"items": []}

# Iterate over the files in the folder
for file_name in os.listdir(folder_path):
    # Check if it is a file
    if os.path.isfile(os.path.join(folder_path, file_name)):
        items_dict["items"].append(file_name.replace('.json', ''))

# Write dictionary to json
with open('items.json', 'w') as f:
    json.dump(items_dict, f, indent=4)
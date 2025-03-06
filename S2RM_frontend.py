import re
import os
import sys
import copy
import json
import math
import time

from dataclasses import asdict
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                               QLabel, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                               QRadioButton, QButtonGroup, QMenuBar, QMenu, QLineEdit, QMessageBox)

from constants import ICE_PER_ICE, MATERIALS_TABLE
from helpers import format_quantities, clamp, resource_path, verify_regexes, TableCols
from porting import OUTPUT_JSON_VERSION, forwardportJson, get_error_message
from S2RM_backend import get_litematica_dir, input_file_to_mats_dict, condense_material, \
    process_exclude_string

PROGRAM_VERSION = "1.3.2"

DARK_INPUT_CELL = "#111a14"
LIGHT_INPUT_CELL = "#b6e0c4"

# Store relative locations, and column widths, of each table header
TABLE_HEADERS = {
    "inputs": {
        "Input Material": 230,
        "Quantity": 210,
        "Exclude": 85
    },
    "outputs": {
        "Raw Material": 230,
        "Quantity": 210,
        "Collected": 85
    },
}
HEADERS_LIST = list(TABLE_HEADERS["inputs"].keys()) + list(TABLE_HEADERS["outputs"].keys())

# Constants for the table columns
INPUT_ITEMS_COL_NUM = 0
INPUT_QUANTITIES_COL_NUM = INPUT_ITEMS_COL_NUM + 1
EXCLUDE_QUANTITIES_COL_NUM = INPUT_QUANTITIES_COL_NUM + 1
RAW_MATERIALS_COL_NUM = 0
RAW_QUANTITIES_COL_NUM = RAW_MATERIALS_COL_NUM + 1
COLLECTIONS_COL_NUM = RAW_QUANTITIES_COL_NUM + 1

FILE_LABEL_TEXT = "Select material list file(s):"
TRUNCATE_LEN = 70
WINDOW_X = 20
WINDOW_Y = 20
WINDOW_WIDTH = 1250
WINDOW_HEIGHT = 850

# Notes
# menu to change default path for input files (saves data to persistent config.json file)
# open window to scroll through all items (with icons) and select which ones should be 'raw' - > would then attempt to Regen the mats list before accepting these changes (catch a recursion error)

# change how the raw mats list is generated to do entity processing then instead of having to redo it everytime an entity is called during runtime. also means u can display all entities and input materials before converting them directly using the raw material json file

# see code camp pyside6 tutorial 5hr 
# For making new applications (or redoing old ones COUGH stemlight) use qt design studio: https://doc.qt.io/qtdesignstudio/studio-installation.html

class S2RMFrontend(QWidget):
    def __init__(self):
        super().__init__()

        self.output_type = "ingots"
        self.ice_type = "ice"
        self.file_paths = []
        
        # Explicitly store table values and table text
        self.tv = TableCols([], [], [], [], [], [])
        self.tt = TableCols([], [], [], [], [], [])

        self.dark_mode = True
        
        self.initUI()

    @property
    def input_vals_text(self):
        return (self.tv.input_quantities, self.tt.input_quantities)
    
    @property
    def exclude_vals_text(self):
        return (self.tv.exclude, self.tt.exclude)
    
    @property
    def raw_vals_text(self):
        return (self.tv.raw_quantities, self.tt.raw_quantities)

    def initUI(self):
        layout = QVBoxLayout()

        # Menu Bar
        self.menu_bar = QMenuBar()
        
        # Store file_menu
        self.file_menu = QMenu("File", self)  
        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        open_json_action = self.file_menu.addAction("Open JSON")
        open_json_action.triggered.connect(self.openJson)
        # Save implies the data can be reloadable
        save_json_action = self.file_menu.addAction("Save JSON")
        save_json_action.triggered.connect(self.saveJson)
        # Export on the other hand doesn't mean it can be reloaded necessarily
        export_to_csv_action = self.file_menu.addAction("Export to CSV")
        export_to_csv_action.triggered.connect(self.exportCSV)
        
        self.menu_bar.addMenu(self.file_menu)
        
        # Store view_menu
        self.view_menu = QMenu("View", self)  
        dark_mode_action = self.view_menu.addAction("Dark Mode")
        dark_mode_action.setCheckable(True)
        dark_mode_action.triggered.connect(self.toggleDarkMode)
        dark_mode_action.setChecked(True)
        self.menu_bar.addMenu(self.view_menu)
        layout.addWidget(self.menu_bar)

        # File Selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel(FILE_LABEL_TEXT)
        file_layout.addWidget(self.file_label)
        self.drop_area = DropArea(self)
        self.drop_area.clicked.connect(self.selectFiles)
        file_layout.addWidget(self.drop_area)
        layout.addLayout(file_layout)

        # Output Type Selection
        output_layout = QHBoxLayout()
        self.ingots_radio = QRadioButton("Ingots")
        self.ingots_radio.setChecked(True)  # Default to ingots
        self.blocks_radio = QRadioButton("Blocks")
        output_layout.addWidget(self.ingots_radio)
        output_layout.addWidget(self.blocks_radio)
        layout.addLayout(output_layout)

        # Ice Type Selection
        ice_layout = QHBoxLayout()
        self.ice_radio = QRadioButton("Only Ice")
        self.ice_radio.setChecked(True)  # Default to Ice
        self.packed_ice_radio = QRadioButton("Freeze Ice")
        ice_layout.addWidget(self.ice_radio)
        ice_layout.addWidget(self.packed_ice_radio)
        layout.addLayout(ice_layout)

        # Radio Button Groups
        self.output_group = QButtonGroup()
        self.output_group.addButton(self.ingots_radio)
        self.output_group.addButton(self.blocks_radio)
        self.output_group.buttonToggled.connect(self.updateOutputType)

        self.ice_group = QButtonGroup()
        self.ice_group.addButton(self.ice_radio)
        self.ice_group.addButton(self.packed_ice_radio)
        self.ice_group.buttonToggled.connect(self.updateIceType)

        # Process and Save Buttons
        button_layout = QHBoxLayout()
        self.process_button = QPushButton("Process")
        self.process_button.clicked.connect(self.processMaterials)
        self.save_button = QPushButton("Save JSON")
        self.save_button.clicked.connect(self.saveJson)
        self.open_json_button = QPushButton("Open JSON")
        self.open_json_button.clicked.connect(self.openJson)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clearMaterials)
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.open_json_button)
        button_layout.addWidget(self.clear_button)
        layout.addLayout(button_layout)

        # Search Bar Layout
        search_layout = QHBoxLayout()
        
        # Raw Material Search Bar
        self.search_label = QLabel("Raw Material Search:")
        self.raw_search_bar = QLineEdit()
        self.raw_search_bar.textChanged.connect(self.updateTableText)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.raw_search_bar)
        
        layout.addLayout(search_layout)

        table_layout = QHBoxLayout()


        # Input Table
        self.input_table = QTableWidget()
        self.input_table.setColumnCount(len(TABLE_HEADERS["inputs"]))
        self.input_table.setHorizontalHeaderLabels(TABLE_HEADERS["inputs"])
        table_layout.addWidget(self.input_table)
        for col, width in enumerate(TABLE_HEADERS["inputs"].values()):
            self.input_table.setColumnWidth(col, width)
        
        input_header = self.input_table.horizontalHeader()
        input_header.setStretchLastSection(True)

        # Raw Materials Table
        self.raw_table = QTableWidget()
        self.raw_table.setColumnCount(len(TABLE_HEADERS["outputs"]))
        self.raw_table.setHorizontalHeaderLabels(TABLE_HEADERS["outputs"])
        table_layout.addWidget(self.raw_table)
        for col, width in enumerate(TABLE_HEADERS["outputs"].values()):
            self.raw_table.setColumnWidth(col, width)
        
        raw_header = self.raw_table.horizontalHeader()
        raw_header.setStretchLastSection(True)
        
        layout.addLayout(table_layout)

        # Enable sorting
        # self.table.setSortingEnabled(True) # XXX doesn't work numerically and doesn't shift out blank cells

        # Current problem with adding sorting to input items:
        #  - starts with exclude cells matching their input item counterparts via the same row index
        #  - when a filter is applied, certain input item names are set to ""
        #  - when updating the text in the table, rows with material == "" are skipped
        #  - inputting a number in the exclude column when a filter is applied

        self.setLayout(layout)
        self.setWindowTitle("S2RM: Schematic to Raw Materials")
        self.setGeometry(WINDOW_X, WINDOW_Y, WINDOW_WIDTH, WINDOW_HEIGHT)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.credits_and_source_label = QLabel()
        self.credits_and_source_label.setAlignment(Qt.AlignCenter)
        self.credits_and_source_label.setOpenExternalLinks(True)
        layout.addWidget(self.credits_and_source_label)
        
        self.updateCreditsLabel()
        self.toggleDarkMode(True)

    def selectFiles(self):
        litematica_dir = get_litematica_dir()
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self, 
            "Select Material List Files", 
            litematica_dir,
            "Supported files (*.litematic *.txt *.csv);;Text/CSV files (*.txt *.csv);;Litematic files (*.litematic);;All files (*.*)"
        )
        
        if file_paths:
            self.file_paths = file_paths
            start_time = time.time_ns()
            self.processSelectedFiles()
            print(f"Time to process files: {(time.time_ns() - start_time) / 1e6:.2f} ms")

    def processSelectedFiles(self, file_paths=None):
        # Reset input items and raw materials
        self.tv.reset()
        self.tt.reset()
        
        # Use the dragged in file paths if none are provided
        if file_paths is not None:
            self.file_paths = file_paths
        
        file_names = ", ".join(os.path.basename(path) for path in self.file_paths)
        # Truncate the file names if they're too long
        if len(file_names) > TRUNCATE_LEN:
            truncated_file_names = file_names[:TRUNCATE_LEN]
            paths_that_fit = truncated_file_names.count(",") + 1
            file_names = file_names[:TRUNCATE_LEN] + f"... (+{len(self.file_paths) - paths_that_fit} more)"
        self.file_label.setText(f"{FILE_LABEL_TEXT} {file_names}")
        
        # Sum all the material lists together into a combined dictionary
        total_input_items = {}
        for file_path in self.file_paths:
            materials_dict = input_file_to_mats_dict(file_path)
            if materials_dict is None:
                print(f"Error reading file: {file_path}. See Above.")
                continue
                
            for material, quantity in materials_dict.items():
                total_input_items[material] = total_input_items.get(material, 0) + quantity
        
        # Sort by quantity in reverse first, then by material name
        sorted_input_items = dict(sorted(total_input_items.items(), key=lambda x: (-x[1], x[0])))
        for material, quantity in sorted_input_items.items():
            self.tv.input_items.append(material)
            self.tv.input_quantities.append(quantity)
    
        # Clear raw materials columns
        self.tv.raw_materials = []
        self.tv.raw_quantities = []
        self.tv.collected_data = []

        self.updateTableText()

    def updateTableText(self, search_term=None, keep_exc_col=False):
        """
        Set the text or widgets from self.tt to the table atfer formatting.
        
        Parameters
        ----------
        search_term : str, optional
            This isn't used and is just there to absorb the search term param sent from the search bar
        """
        # Ensure all text is up to date
        self.tt = copy.deepcopy(self.tv)

        # Break down large values into shulker boxes and stacks
        format_quantities(self.tv.input_items, self.input_vals_text)
        format_quantities(self.tv.raw_materials, self.raw_vals_text)
        
        # Check all user inputted exclude values, and update the exclude column accordingly
        if not keep_exc_col:
            self.getExcludeVals()
        self.format_exclude_column()

        # Check for search terms in the raw materials search bar
        self.filterMaterials()

        # Set the new table length to the maximum of the input items and raw materials
        self.input_table.setRowCount(len(self.tt.input_items))
        self.raw_table.setRowCount(len(self.tt.raw_materials))

        # Set new values for the input materials table
        for row, material in enumerate(self.tt.input_items):
            self.__set_input_materials_cell(row, INPUT_ITEMS_COL_NUM, material.replace("$", "")) # Remove $ from encoded entities
            self.__set_input_materials_cell(row, INPUT_QUANTITIES_COL_NUM, self.tt.input_quantities[row])
            self.__set_exclude_text_cell(row, self.tt.exclude[row])

        # Set new values for the raw materials table
        for row, material in enumerate(self.tt.raw_materials):
            self.__set_raw_materials_cell(row, RAW_MATERIALS_COL_NUM, self.tt.raw_materials[row])
            self.__set_raw_materials_cell(row, RAW_QUANTITIES_COL_NUM, self.tt.raw_quantities[row])
            self.__add_checkbox(row, material)

        # Delete data after new input items
        for row in range(len(self.tt.input_items), self.input_table.rowCount()):
            self.__set_input_materials_cell(row, INPUT_ITEMS_COL_NUM, "")
            self.__set_input_materials_cell(row, INPUT_QUANTITIES_COL_NUM, "")
            self.input_table.setCellWidget(row, EXCLUDE_QUANTITIES_COL_NUM, None)
        
        # Delete data after new raw materials
        for row in range(len(self.tt.raw_materials), self.raw_table.rowCount()):
            self.__set_raw_materials_cell(row, RAW_MATERIALS_COL_NUM, "")
            self.__set_raw_materials_cell(row, RAW_QUANTITIES_COL_NUM, "")
            self.raw_table.setCellWidget(row, COLLECTIONS_COL_NUM, None)

    def filterMaterials(self):
        """Checks comma separated regex search terms against the raw materials."""
        # Remove any blank or invalid search terms
        raw_search_terms = verify_regexes(self.raw_search_bar.text())

        raw_cols = [self.tt.raw_quantities, self.tt.collected_data]
        self.__filter_column(raw_search_terms, self.tt.raw_materials, raw_cols)

    def getExcludeVals(self):
        """Resets current exclude vals, and reads in new input from user in the exclude column."""
        self.tv.exclude = []
        for row, material in enumerate(self.tv.input_items):
            # Get the value from the third column (number input)
            if (excl_cell := self.input_table.item(row, EXCLUDE_QUANTITIES_COL_NUM)) is None:
                exclude_text = "0"
            else:
                exclude_text = excl_cell.text()
                if not exclude_text:
                    exclude_text = "0"

            exclude_value = 0
            
            required_quantity = self.tv.input_quantities[row]
            # Try converting the exclude val to a float and then clamp it
            try:
                exclude_value = clamp(float(exclude_text), 0, required_quantity)
            # Otherwise process the custom text input
            except (ValueError, TypeError):
                if exclude_text.strip().lower() in ["all", "a"]:
                    exclude_value = required_quantity
                # Check for other valid input formats listing stacks and shulker boxes (e.g., '1s 2sb')
                elif (exclude_value := process_exclude_string(exclude_text, material)) == -1:
                    # If user enters something proper invalid reset to 0
                    exclude_value = 0
                
                exclude_value = clamp(exclude_value, 0, required_quantity)

            # Add excluded value and text to the list
            self.tv.exclude.append(exclude_value)   

    def format_exclude_column(self):
        """Format  the exclude input item column into shulker boxes and stacks."""
        self.tt.exclude = self.tv.exclude.copy()
        format_quantities(self.tv.input_items, self.exclude_vals_text, is_exclude_col=True)
        
        # Change formatted values to just be 'All' if an entire input quantity is satisfied
        for row, input_quantity in enumerate(self.tv.input_quantities):
            if self.tv.exclude[row] == input_quantity:
                self.tt.exclude[row] = "All"

    def processMaterials(self):
        if not self.file_paths:
            return

        # Update formatting
        self.updateTableText()

        # Get the dictionary of total raw materials needed
        self.__get_total_mats_from_input()

        # Update values (and concomitantly formatting)
        self.updateTableText()

    def saveJson(self):
        """Save object data to a JSON-compatible dictionary."""
        table_dict = {}
        table_dict["version"] = OUTPUT_JSON_VERSION

        # Add config attributes in specific order with appropriate defaults
        self.__add_with_default(table_dict, "file_paths", "material_list_paths", [])
        self.__add_with_default(table_dict, "output_type", "output_type", "ingots")
        self.__add_with_default(table_dict, "ice_type", "ice_type", "ice")
        
        # Add only the unformatted backend table data (raw values)
        table_dict["tv"] = asdict(self.tv)
        table_dict["tt"] = asdict(self.tt)

        # Save the JSON file to the desktop or elsewhere
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self, "Save JSON File",os.path.join(desktop_path, "materials_table.json"),
            "JSON files (*.json);;All files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump(table_dict, f, indent=4)
                print(f"JSON saved successfully to: {file_path}")
            except Exception as e:
                print(f"Error saving JSON: {e}")
   
    def openJson(self):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")  # Default to Desktop
        file_dialog = QFileDialog()
        json_file_path, _ = file_dialog.getOpenFileName(
            self, "Open JSON File", desktop_path, "JSON files (*.json);;All files (*.*)"
        )
        if json_file_path:
            with open(json_file_path, "r") as f:
                table_dict = json.load(f)

                version = table_dict.get("version", "unspecified")
                if version != OUTPUT_JSON_VERSION:
                    # forwardportJson returns an error code (positive int) if something goes wrong
                    if ec := forwardportJson(table_dict, version):
                        QMessageBox.warning(
                            self,
                            "Incompatible Materials Table",
                            get_error_message(ec, version),
                        )
                        return

            print(f"JSON opened successfully from: {json_file_path}")

            # Reset the tables
            self.input_table.setRowCount(0)
            self.raw_table.setRowCount(0)
            self.tv.reset()
            self.tt.reset()
            
            if "output_type" in table_dict:
                self.output_type = table_dict["output_type"]
                self.__set_radio_button(self.output_type, ["blocks", "ingots"],
                                        [self.blocks_radio, self.ingots_radio])
            if "ice_type" in table_dict:
                self.ice_type = table_dict["ice_type"]
                self.__set_radio_button(self.ice_type, ["ice", "freeze"],
                                        [self.packed_ice_radio, self.ice_radio])

            # Load the table values from legacy version 8
            if "table_values" in table_dict:
                self.tv = TableCols(**table_dict["table_values"])

                self.updateTableText(keep_exc_col=True)

            # Updated version 8 as of v1.3.2
            if "tv" in table_dict:
                self.tv = TableCols(**table_dict["tv"])
            
            if "tt" in table_dict:
                self.tt = TableCols(**table_dict["tt"])

            self.file_paths = [json_file_path]
            self.file_label.setText(f"{FILE_LABEL_TEXT} {os.path.basename(json_file_path)}")
        else:
            print("No file selected")

    def exportCSV(self):
        """Export the current table text to a CSV file."""
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self, "Export CSV File", os.path.join(desktop_path, "raw_materials_table.csv"),
            "CSV files (*.csv);;All files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, "w") as f:
                    # Write headers
                    f.write(",".join(TABLE_HEADERS) + "\n")

                    # Get the maximum number of rows
                    max_rows = max(len(self.tt.input_items), len(self.tt.input_quantities), len(self.tt.exclude),
                                len(self.tt.raw_materials), len(self.tt.raw_quantities), len(self.tt.collected_data))
                                    
                    for row in range(max_rows):
                        row_data = [
                            self.tt.input_items[row] if row < len(self.tt.input_items) else "",
                            self.tt.input_quantities[row] if row < len(self.tt.input_quantities) else "",
                            self.tt.exclude[row] if row < len(self.tt.exclude) else "",
                            self.tt.raw_materials[row] if row < len(self.tt.raw_materials) else "",
                            self.tt.raw_quantities[row] if row < len(self.tt.raw_quantities) else "",
                            self.tt.collected_data[row] if row < len(self.tt.collected_data) else ""
                        ]
                        f.write(",".join(map(str, row_data)) + "\n")
                print(f"CSV saved successfully to: {file_path}")
            except Exception as e:
                print(f"Error saving CSV: {e}")

    def clearMaterials(self):
        # Clear/reset the tables
        self.input_table.setRowCount(0)
        self.raw_table.setRowCount(0)
        self.tv.reset()
        self.tt.reset()
        self.updateTableText()
        
        # Reset config attributes
        self.file_paths = []
        self.output_type = "ingots"
        self.ingots_radio.setChecked(True)
        self.ice_type = "ice"
        self.ice_radio.setChecked(True)
        self.file_label.setText(FILE_LABEL_TEXT)

######### Helper and Private Methods #########

    def __filter_column(self, search_terms: list[str], materials: list[str],
                        related_lists: list[list]):
        """
        Filter a single column of the table given a list of search terms and a material-quantity list.
        """
        # If search terms are invalid or empty, return
        if not search_terms:
            return
        
        # Pop elements from the end to avoid index errors
        for i in range(len(materials) - 1, -1, -1):
            # If not a single search term matches the material, remove it
            if not any(re.search(search, materials[i], re.IGNORECASE) for search in search_terms):
                materials.pop(i)
                # Remove elements from related lists too, e.g. input_quantities and exclude
                for related_list in related_lists:
                    related_list.pop(i)

    def __add_checkbox(self, row, material):
        """Add a checkbox to the table at the given row."""
        # Add checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(self.tv.collected_data[row])
        checkbox.stateChanged.connect(lambda state, row=row: self.updateCollected(row, state))
        
        # Create a widget to center the checkbox
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0) # Remove margins

        self.raw_table.setCellWidget(row, COLLECTIONS_COL_NUM, checkbox_widget)

    def __get_total_mats_from_input(self) -> None:
        # Clear the raw materials table
        self.tv.raw_materials = []
        self.tv.raw_quantities = []
        self.tv.collected_data = []
        
        total_materials = {}
        for row, input_material in enumerate(self.tv.input_items):
            if input_material in MATERIALS_TABLE:
                input_quantity = self.tv.input_quantities[row]
                exclude_quantity = self.tv.exclude[row]
                for raw_material in MATERIALS_TABLE[input_material]:
                    raw_name, raw_quantity = raw_material["item"], raw_material["quantity"]

                    # Keep or 'freeze' the original ice type if specified
                    if re.match(r"(packed|blue)_ice$", input_material):
                        raw_name, raw_quantity = self.__handle_ice_type(input_material, raw_quantity)
                                                   
                    raw_needed = raw_quantity * (input_quantity - exclude_quantity)
                    total_materials[raw_name] = total_materials.get(raw_name, 0) + raw_needed
            # Check if the input material is an encoded unfiltered entity
            elif input_material.startswith("$"):
                input_entity = input_material[1:]

                entity_quantity = self.tv.input_quantities[row]
                exclude_quantity = self.tv.exclude[row]
                
                raw_needed = entity_quantity - exclude_quantity
                total_materials[input_entity] = total_materials.get(input_entity, 0) + raw_needed
            else:
                raise ValueError(f"Material {input_material} not found in materials table. Row: {row}.")

        # Round final quantities up
        for material, quantity in total_materials.items():
            total_materials[material] = math.ceil(quantity)

        # Post-process to handle blocks and remaining ingots
        if self.output_type == "blocks":
            processed_materials = {}
            
            # Compact ingots/resource items into block form
            for material, quantity in total_materials.items():
                condense_material(processed_materials, material, quantity)

            total_materials = processed_materials
            
        # Sort by quantity (descending) then by material name (ascending)
        total_materials = dict(sorted(total_materials.items(), key=lambda x: (-x[1], x[0])))

        for material, quantity in total_materials.items():
            self.tv.raw_materials.append(material)
            self.tv.raw_quantities.append(quantity)
            self.tv.collected_data.append(False)

    def __handle_ice_type(self, input_ice_type, ice_quantity):
        """
        Returns ice as either its original type or as decompressed normal ice.
        
        The way this works is an input material such as packed or blue ice is input, as well as 
        ice_quantity, which is the amount of ice needed for input_ice_type.
        """
        if self.ice_type == "freeze":
            if input_ice_type == "packed_ice":
                raw_ice_name = "packed_ice"
                raw_ice_quantity = ice_quantity / ICE_PER_ICE
            elif input_ice_type == "blue_ice":
                raw_ice_name = "blue_ice"
                raw_ice_quantity = ice_quantity / (ICE_PER_ICE ** 2)
        else:
            return "ice", ice_quantity
                
        return raw_ice_name, raw_ice_quantity

    ################ GUI/Style Methods ################
    
    def updateOutputType(self):
        self.output_type = "ingots" if self.ingots_radio.isChecked() else "blocks"
            
    def updateIceType(self):
        self.ice_type = "ice" if self.ice_radio.isChecked() else "freeze"
    
    def updateCollected(self, row, state):
        self.tv.collected_data[row] = Qt.CheckState(state) == Qt.CheckState.Checked

    def toggleDarkMode(self, checked):
        self.dark_mode = checked
        if self.dark_mode:
            self.setDarkMode()
        else:
            self.setLightMode()

    def setDarkMode(self):
        app.setStyle('Fusion')
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

        # Apply dark mode to specific widgets
        self.drop_area.setStyleSheet("QPushButton { background-color: #353535; color: white; border: 1px solid #555; border-radius: 3px; }")
        self.process_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.save_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.open_json_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.clear_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.raw_search_bar.setStyleSheet("QLineEdit { background-color: #191919; color: white; }")
        self.input_table.setStyleSheet("""
            QTableWidget { background-color: #191919; color: white; gridline-color: #353535;}
            QHeaderView::section { background-color: #353535; color: white; }
            QTableCornerButton::section { background-color: #353535; }
        """)
        self.raw_table.setStyleSheet("""
            QTableWidget { background-color: #191919; color: white; gridline-color: #353535;}
            QHeaderView::section { background-color: #353535; color: white; }
            QTableCornerButton::section { background-color: #353535; }
        """)

        self.menu_bar.setStyleSheet("""
            QMenuBar { background-color: #252525; color: white; }
            QMenuBar::item { background-color: #252525; color: white; }  # Style the menu items
            QMenuBar::item:selected { background-color: #4A4A4A; }
            QMenu { background-color: #252525; color: white; }
            QMenu::item { background-color: #252525; color: white; }  # Style the menu items
            QMenu::item:selected { background-color: #4A4A4A; }
        """)

        # Apply styles to the menus
        self.file_menu.setStyleSheet("""
            QMenu { background-color: #353535; color: white; }
            QMenu::item { background-color: #353535; color: white; }
            QMenu::item:selected { background-color: #4A4A4A; }
        """)

        self.view_menu.setStyleSheet("""
            QMenu { background-color: #353535; color: white; }
            QMenu::item { background-color: #353535; color: white; }
            QMenu::item:selected { background-color: #4A4A4A; }
        """)
        
        self.setEditableCellStyles(DARK_INPUT_CELL)  # Dark mode cell color

        # Make credits and source text brighter
        self.updateCreditsLabel()

    def setLightMode(self):
        app.setStyle('windowsvista')
        
        self.setPalette(QApplication.style().standardPalette())

        # Reset styles for specific widgets
        self.drop_area.setStyleSheet("")
        self.drop_area.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 3px; }")
        self.process_button.setStyleSheet("")
        self.save_button.setStyleSheet("")
        self.open_json_button.setStyleSheet("")
        self.clear_button.setStyleSheet("")
        self.raw_search_bar.setStyleSheet("")
        self.input_table.setStyleSheet("")
        self.raw_table.setStyleSheet("")

        # Reset menu styles
        self.menu_bar.setStyleSheet("")
        self.file_menu.setStyleSheet("")
        self.view_menu.setStyleSheet("")
        
        self.setEditableCellStyles(LIGHT_INPUT_CELL)

        # Reset credits and source text color
        self.updateCreditsLabel()
    
    def setEditableCellStyles(self, hex_color):
        """Sets background color for editable cells: currently only 'exclude' in the input table."""
        for row in range(self.input_table.rowCount()):
            number_item = self.input_table.item(row, EXCLUDE_QUANTITIES_COL_NUM)
            if number_item and number_item.flags() & Qt.ItemIsEditable:
                number_item.setBackground(QColor(hex_color))

    def updateCreditsLabel(self):
        # Choose colors based on mode
        if self.dark_mode:
            link_color = "#ADD8E6" # Light blue for dark mode
            version_color = "#FFD700" # Gold for dark mode
        else:
            link_color = "#0066CC" # More pleasant dark blue for light mode
            version_color = "#FF4500" # Slightly darker orange for light mode
        
        # Set the text with inline styling for the links
        non_breaking_spaces = "&nbsp;" * 10
        self.credits_and_source_label.setText(
            f'<a style="color: {link_color};" '
            f'href="https://youtube.com/ncolyer">Made by ncolyer</a> | '
            f'<span style="color: {version_color};">Version: {PROGRAM_VERSION}</span> | '
            f'<a style="color: {link_color};" '
            f'href="https://github.com/ncolyer11/S2RM">Source</a>{non_breaking_spaces}'
        )

    def __set_exclude_text_cell(self, row, quantity: int | str):
        """
        Set the exclude text cell in the table.
        
        Parameters
        ----------
        row : int
            The row number to set the cell in.
        quantity : int | str
            The quantity to set in the cell, can be a formatted string with sb and stacks breakdown.
        """
        cell_colour = DARK_INPUT_CELL if self.dark_mode else LIGHT_INPUT_CELL
        number_item = QTableWidgetItem(str(quantity))  # Default value or you can leave it empty
        number_item.setFlags(number_item.flags() | Qt.ItemIsEditable)  # Make the cell editable
        number_item.setBackground(QColor(cell_colour))
        self.input_table.setItem(row, EXCLUDE_QUANTITIES_COL_NUM, number_item)      

    def __set_input_materials_cell(self, row, col, text):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Make the cell non-editable
        self.input_table.setItem(row, col, item)

    def __set_raw_materials_cell(self, row, col, text):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.raw_table.setItem(row, col, item)

    def __add_with_default(self, table_dict, attr_name, key_name, default_value):
        if hasattr(self, attr_name):
            table_dict[key_name] = getattr(self, attr_name)
        else:
            table_dict[key_name] = default_value

    @staticmethod
    def __set_radio_button(set_to_state, bool_states: list, radio_buttons: list):
        """
        Sets the radio button to the specified state.
        
        Parameters
        ----------
        set_to_state : bool
            The state to set the radio button to.
        bool_states : list
            The boolean states corresponding to the radio buttons.
        radio_buttons : list
            The radio buttons to set.
        """
        if set_to_state == bool_states[0]:
            radio_buttons[0].setChecked(True)
        elif set_to_state == bool_states[1]:
            radio_buttons[1].setChecked(True)
        else:
            raise ValueError(f"Invalid state: {set_to_state}")

class DropArea(QPushButton):
    def __init__(self, parent=None):
        super().__init__("Drop files here or click", parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(40)
        self.parent = parent

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            # Store original stylesheet to restore later
            self._original_stylesheet = self.styleSheet()
            # Add highlighted border when dragging over
            if self.parent.dark_mode:
                self.setStyleSheet("QPushButton { background-color: #454545; color: white; border: 2px solid #42a5f5; }")
            else:
                self.setStyleSheet("QPushButton { background-color: #e3f2fd; border: 2px solid #42a5f5; }")

    def dragLeaveEvent(self, event):
        # Restore original stylesheet
        self.setStyleSheet(self._original_stylesheet)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                file_ext = file_path.lower().split('.')[-1]
                if file_ext in ['txt', 'csv', 'litematic']:
                    file_paths.append(file_path)
            
            if file_paths:
                self.parent.processSelectedFiles(file_paths)
            
            event.acceptProposedAction()
        
        # Restore original stylesheet
        self.setStyleSheet(self._original_stylesheet)

def start():
    global app
    app = QApplication(sys.argv)
    app_icon = QIcon(resource_path("icon.ico"))
    app.setWindowIcon(app_icon)
    app.setStyle('Fusion')
    window = S2RMFrontend()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    start()

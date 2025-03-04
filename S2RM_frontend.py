import re
import os
import sys
import copy
import json
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                               QLabel, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                               QRadioButton, QButtonGroup, QMenuBar, QMenu, QLineEdit, QMessageBox)

from constants import ICE_PER_ICE
from helpers import format_quantities, clamp, resource_path, verify_regexes
from porting import OUTPUT_JSON_VERSION, forwardportJson, get_error_message
from dataclasses import dataclass, asdict
from S2RM_backend import process_material_list, condense_material, process_exclude_string, \
    process_litematic_file

# XXX
# left search bar resets when you use the right one
# ^^ FIX this by making a display table dict and a backend table dict so you're not storing formatted text as your actual values

PROGRAM_VERSION = "1.3.0"

DARK_INPUT_CELL = "#111a14"
LIGHT_INPUT_CELL = "#b6e0c4"

TABLE_HEADERS = ["Input", "Quantity", "Exclude", "Raw Material", "Quantity", "Collected"]
FILE_LABEL_TEXT = "Select material list file(s):"

# Constants for the table columns
INPUT_ITEMS_COL_NUM = 0
INPUT_QUANTITIES_COL_NUM = INPUT_ITEMS_COL_NUM + 1
EXCLUDE_QUANTITIES_COL_NUM = INPUT_QUANTITIES_COL_NUM + 1
RAW_MATERIALS_COL_NUM = 3
RAW_QUANTITIES_COL_NUM = RAW_MATERIALS_COL_NUM + 1
COLLECTIONS_COL_NUM = 5

@dataclass
class TableCols:
    input_items: list
    input_quantities: list
    exclude: list
    raw_materials: list
    raw_quantities: list
    collected_data: list

    def reset(self):
        self.input_items = []
        self.input_quantities = []
        self.exclude = []
        self.raw_materials = []
        self.raw_quantities = []
        self.collected_data = []

class S2RMFrontend(QWidget):
    def __init__(self):
        super().__init__()

        self.output_type = "ingots"
        self.ice_type = "ice"
        
        self.input_items = {}
        self.exclude_text = []
        self.exclude_values = []
        self.collected_data = {}
        # Explicitly store table text and table values
        self.tt = TableCols([], [], [], [], [], [])
        self.tv = TableCols([], [], [], [], [], [])

        self.dark_mode = True
        
        # Load the raw materials table
        with open(resource_path("raw_materials_table.json"), "r") as f:
            self.materials_table = json.load(f)

        self.initUI()

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
        
        # New Input Materials Search Bar
        self.input_search_label = QLabel("Input Material Search:")
        self.input_search_bar = QLineEdit()
        self.input_search_bar.textChanged.connect(self.updateTableText)
        search_layout.addWidget(self.input_search_label)
        search_layout.addWidget(self.input_search_bar)

        # Existing Raw Material Search Bar
        self.search_label = QLabel("Raw Material Search:")
        self.raw_search_bar = QLineEdit()
        self.raw_search_bar.textChanged.connect(self.updateTableText)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.raw_search_bar)
        
        layout.addLayout(search_layout)

        # Table Display
        self.table = QTableWidget()
        self.table.setColumnCount(len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        layout.addWidget(self.table)
        self.table.setColumnWidth(INPUT_ITEMS_COL_NUM, 210)
        self.table.setColumnWidth(INPUT_QUANTITIES_COL_NUM, 200)
        self.table.setColumnWidth(EXCLUDE_QUANTITIES_COL_NUM, 80)
        self.table.setColumnWidth(RAW_MATERIALS_COL_NUM, 170)
        self.table.setColumnWidth(RAW_QUANTITIES_COL_NUM, 200)
        self.table.setColumnWidth(COLLECTIONS_COL_NUM, 80)
        
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        # Enable sorting
        # self.table.setSortingEnabled(True) # XXX doesn't work numerically and doesn't shift out blank cells

        self.setLayout(layout)
        self.setWindowTitle("S2RM: Schematic to Raw Materials")
        self.setGeometry(20, 20, 1150, 850)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.credits_and_source_label = QLabel()
        self.credits_and_source_label.setAlignment(Qt.AlignCenter)
        self.credits_and_source_label.setOpenExternalLinks(True)
        layout.addWidget(self.credits_and_source_label)
        
        self.updateCreditsLabel()
        self.toggleDarkMode(True)

    def selectFiles(self):
        litematica_dir = self.get_litematica_dir()
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self, 
            "Select Material List Files", 
            litematica_dir,
            "Supported files (*.litematic *.txt *.csv);;Text/CSV files (*.txt *.csv);;Litematic files (*.litematic);;All files (*.*)"
        )
        
        if file_paths:
            self.processSelectedFiles(file_paths)

    def processSelectedFiles(self, file_paths):
        # Reset input items and raw materials
        self.tv.input_items = []
        self.tv.input_quantities = []
        self.tv.exclude = []
        self.file_paths = file_paths
        file_names = ", ".join(os.path.basename(path) for path in file_paths)
        self.file_label.setText(f"{FILE_LABEL_TEXT} {file_names}")
        
        input_items = {}
        for file_path in file_paths:
            # Check if it's a litematic file or text/csv
            if file_path.lower().endswith('.litematic'):
                # Process litematic file
                materials_dict = process_litematic_file(file_path)
            else:
                # Process text/csv file with your existing function
                materials_dict = process_material_list(file_path)
                
            for material, quantity in materials_dict.items():
                input_items[material] = input_items.get(material, 0) + quantity # Sum dicts
        
        sorted_input_items = dict(sorted(input_items.items(), key=lambda x: (-x[1], x[0])))
        for material, quantity in sorted_input_items.items():
            self.input_items.append(material)
            self.input_quantities.append(quantity)
            self.exclude.append(0)
    
        # Clear raw materials columns
        self.tv.raw_materials = []
        self.tv.raw_quantities = []
        self.tv.collected_data = []

    def updateTableText(self, search_term=None):
        """
        Set the text or widgets from self.tt to the table atfer formatting.
        
        Parameters
        ----------
        search_term : str, optional
            This isn't used and is just there to absorb the search term param sent from the search bar
        """
        # Ensure all text is up to date
        self.tt = copy.deepcopy(self.tv)

        # Check for search terms in the input and raw materials search bars
        self.filterMaterials()

        # Break down large values into shulker boxes and stacks
        self.format_columns()

        # Set the new table length to the maximum of the input items and raw materials
        self.table.setRowCount(max(len(self.tt.input_items), len(self.tt.raw_materials)))
        
        # Check all user inputted exclude values, and update the exclude column accordingly
        self.getExcludeVals()

        # Set new values for the input materials table
        for row in range(len(self.tt.input_items)):
            self.__set_materials_cell(row, INPUT_ITEMS_COL_NUM, self.tt.input_items[row])
            self.__set_materials_cell(row, INPUT_QUANTITIES_COL_NUM, self.tt.input_quantities[row])
            self.__set_exclude_text_cell(row, self.tt.exclude_text[row])

        # Set new values for the raw materials table
        for row, material in enumerate(self.tt.raw_materials):
            self.__set_materials_cell(row, RAW_MATERIALS_COL_NUM, self.tt.raw_materials[row])
            self.__set_materials_cell(row, RAW_QUANTITIES_COL_NUM, self.tt.raw_quantities[row])
            self.__add_checkbox(row, material)

        # Delete data after new input items
        for row in range(len(self.tt.input_items), self.table.rowCount()):
            self.__set_materials_cell(row, INPUT_ITEMS_COL_NUM, "")
            self.__set_materials_cell(row, INPUT_QUANTITIES_COL_NUM, "")
            self.table.setCellWidget(row, EXCLUDE_QUANTITIES_COL_NUM, None)
        
        # Delete data after new raw materials
        for row in range(len(self.tt.raw_materials), self.table.rowCount()):
            self.__set_materials_cell(row, RAW_MATERIALS_COL_NUM, "")
            self.__set_materials_cell(row, RAW_QUANTITIES_COL_NUM, "")
            self.table.setCellWidget(row, COLLECTIONS_COL_NUM, None)

    def format_columns(self):
        """Format the columns of the to break down quantities into shulker boxes and stacks."""
        format_quantities(self.tt.input_items, self.tt.input_quantities)
        format_quantities(self.tt.input_items, self.tv.exclude, shorthand=True)
        format_quantities(self.tt.raw_materials, self.tt.raw_quantities)

    def filterMaterials(self):
        """Checks comma separated regex search terms against the raw materials."""
        # Remove any blank search terms
        input_search_terms = verify_regexes(self.input_search_bar.text())
        raw_search_terms = verify_regexes(self.raw_search_bar.text())

        self.__filter_column(input_search_terms, self.tt.input_items, self.tt.input_quantities,
                             self.tt.exclude)
        self.__filter_column(raw_search_terms, self.tt.raw_materials, self.tt.raw_quantities,
                             self.tt.collected_data)
        
    def __filter_column(self, search_terms: list[str], materials: list[str],
                        related_lists: list[list]):
        """
        Filter a single column of the table given a list of search terms and a material-quantity list.
        """
        for i, material in enumerate(materials):
            # If not a single search term matches the material, remove it
            if not any(re.search(search, material, re.IGNORECASE) for search in search_terms):
                materials.pop(i)
                # Remove elements from related lists too, e.g. input_quantities and exclude
                for related_list in related_lists:
                    related_list.pop(i)

    def __add_checkbox(self, row, material):
        """Add a checkbox to the table at the given row."""
        # Add checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(self.collected_data.get(material, False))
        checkbox.stateChanged.connect(lambda state, mat=material: self.updateCollected(mat, state))
        
        # Create a widget to center the checkbox
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0) # Remove margins

        self.table.setCellWidget(row, COLLECTIONS_COL_NUM, checkbox_widget)

    def getExcludeVals(self):
        self.tv.exclude = []
        self.tt.exclude = []
        for row, material in self.tv.input_items:
            # Get the value from the third column (number input)
            exclude_value = 0
            exclude_text = self.table.item(row, EXCLUDE_QUANTITIES_COL_NUM).text()
            
            required_quantity = self.tv.input_quantities[row]
            # Try converting the exclude val to a float and then clamp it
            try:
                exclude_value = clamp(float(exclude_text), 0, required_quantity)
            # Otherwise process the custom text input
            except ValueError:
                if exclude_text.strip().lower() in ["all", "a"]:
                    exclude_text = "All"
                    exclude_value = required_quantity
                # Check for other valid input formats listing stacks and shulker boxes (e.g., '1s 2sb')
                elif (exclude_value := process_exclude_string(exclude_text, material)) == -1:
                    # If user enters something proper invalid reset to 0
                    exclude_text = "0"
                    exclude_value = 0
                
                if (exclude_value := clamp(exclude_value, 0, required_quantity)) == required_quantity:
                    exclude_text = "All"

            # Add excluded value and text to the list
            self.tv.exclude.append(exclude_value)
            self.tt.exclude_text.append(exclude_text)

    def processMaterials(self):
        if not hasattr(self, "file_paths"):
            return
        
        json_file_path = None
        # Handle string or list with single string
        if isinstance(self.file_paths, str) and self.file_paths.endswith(".json"):
            json_file_path = self.file_paths
        elif isinstance(self.file_paths, list) and len(self.file_paths) == 1 and \
             isinstance(self.file_paths[0], str) and self.file_paths[0].endswith(".json"):
            json_file_path = self.file_paths[0]

        # If self.file_paths is a single .json file, extract the new self.input_items
        if json_file_path is not None:
            self.__extract_input_items_from_json(json_file_path)

        # Get the dictionary of total raw materials needed
        total_materials = self.__get_total_mats_from_input()

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
        self.total_materials = total_materials

    def filterInputMaterials(self, search_term: str) -> tuple[dict[str, int], dict[str, str]]:
        """Checks comma separated regex search terms against the input materials."""
        # Remove any blank search terms
        current_exclude_dict = {material: exclude_text for material, exclude_text in zip(self.input_items, self.exclude_text)}
        if not (search_terms := [term.strip().strip("'") for term in search_term.split(",") if term.strip()]):
            return self.input_items, current_exclude_dict
        if not (valid_search_terms := verify_regexes(search_terms)):
            return self.input_items, current_exclude_dict

        filtered_inputs = {}
        exclude_dict = {}
        for (material, quantity), exclude_text in zip(self.input_items.items(), self.exclude_text):
            if any(re.search(search, material, re.IGNORECASE) for search in valid_search_terms):
                filtered_inputs[material] = quantity
                exclude_dict[material] = exclude_text
            else:
                print(f"Excluding {material}")

        return filtered_inputs, exclude_dict

    def filterMaterials(self, search_term):
        """Checks comma separated regex search terms against the raw materials."""
        # Remove any blank search terms
        if not (search_terms := [term.strip().strip("'") for term in search_term.split(",") if term.strip()]):
            return self.total_materials
        if not (valid_search_terms := verify_regexes(search_terms)):
            return self.total_material

        filtered_materials = {}
        if hasattr(self, "total_materials"):
            for material, quantity in self.total_materials.items():
                if any(re.search(search, material, re.IGNORECASE) for search in valid_search_terms):
                    filtered_materials[material] = quantity
        
        return filtered_materials

    def saveJson(self):
        """Save object data to a JSON-compatible dictionary."""
        table_dict = {}
        table_dict["version"] = OUTPUT_JSON_VERSION

        # Add config attributes in specific order with appropriate defaults
        self.__add_with_default(table_dict, "file_paths", "material_list_paths", [])
        self.__add_with_default(table_dict, "output_type", "output_type", "")
        self.__add_with_default(table_dict, "ice_type", "ice_type", "")
        
        # Add only the unformatted backend table data (raw values)
        table_dict["table_values"] = asdict(self.tv)

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
   
    def openJson(self): # XXX update to format 8 that just stores self.tv
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

            # Reset the table
            self.table.setRowCount(0)
            self.tv.reset()
            self.tt.reset()
            
            if "output_type" in table_dict:
                self.output_type = table_dict["output_type"]
                self.__set_radio_button(self.output_type, ["blocks", "ingots"],
                                        [self.blocks_radio, self.ingots_radio])
            if "ice_type" in table_dict:
                self.ice_type = table_dict["ice_type"]
                self.__set_radio_button(self.ice_type, ["freeze", "ice"],
                                        [self.packed_ice_radio, self.ice_radio])

            if "table_values" in table_dict:
                self.tv = TableCols(**table_dict["table_values"])
                self.updateTableText()

            self.file_paths = json_file_path
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
        # Clear/reset the table
        self.table.setRowCount(0)
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

    def get_litematica_dir(self):
        """Gets the Litematica directory, trying the S: drive first, then %appdata%."""
        s_drive_path = r"S:\mc\.minecraft\config\litematica"
        if os.path.exists(s_drive_path):
            return s_drive_path
        appdata_path = os.getenv('APPDATA')
        if appdata_path:
            appdata_litematica_path = os.path.join(appdata_path, ".minecraft", "config", "litematica")
            if os.path.exists(appdata_litematica_path):
                return appdata_litematica_path
        return "" # Return an empty string if directory not found

    def updateOutputType(self):
        self.output_type = "ingots" if self.ingots_radio.isChecked() else "blocks"
            
    def updateIceType(self):
        self.ice_type = "ice" if self.ice_radio.isChecked() else "freeze"
    
    def updateCollected(self, material, state):
        self.collected_data[material] = Qt.CheckState(state) == Qt.CheckState.Checked

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
        self.table.setStyleSheet("""
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
        self.table.setStyleSheet("")

        # Reset menu styles
        self.menu_bar.setStyleSheet("")
        self.file_menu.setStyleSheet("")
        self.view_menu.setStyleSheet("")
        
        self.setEditableCellStyles(LIGHT_INPUT_CELL)

        # Reset credits and source text color
        self.updateCreditsLabel()
    
    def setEditableCellStyles(self, hex_color):
        """Sets background color for editable cells."""
        for row in range(self.table.rowCount()):
            number_item = self.table.item(row, EXCLUDE_QUANTITIES_COL_NUM)
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

    def __extract_input_items_from_json(self, json_file_path: str):
        """Extracts the input items from a JSON file and updates self.file_paths accordingly."""
        try:
            with open(json_file_path, "r") as f:
                table_dict = json.load(f)
                if "input_items" in table_dict and "input_quantities" in table_dict:
                    self.input_items = {item: quantity for item, quantity in
                                        zip(table_dict["input_items"], table_dict["input_quantities"])}
                    
                    # Ensure it's sorted
                    self.input_items = dict(sorted(self.input_items.items(),
                                                    key=lambda x: (-x[1], x[0])))
                else:
                    print("No input items found in JSON file.")
                    return
        except Exception as e:
            print(f"An error occurred: {e}")
            return
        
        self.file_paths = json_file_path

    def __get_total_mats_from_input(self) -> dict:
        total_materials = {}
        for input_item_idx, (material, quantity) in enumerate(self.input_items.items()):
            if material in self.materials_table:
                exclude_quantity = self.exclude_values[input_item_idx]
                for raw_material in self.materials_table[material]:
                    rm_name, rm_quantity = raw_material["item"], raw_material["quantity"]

                    # Keep or 'freeze' the original ice type if specified
                    if self.ice_type == "freeze":
                        if material == "packed_ice":
                            rm_name = "packed_ice"
                            rm_quantity = rm_quantity / ICE_PER_ICE
                        elif material == "blue_ice":
                            rm_name = "blue_ice"
                            rm_quantity = rm_quantity / (ICE_PER_ICE ** 2)
                                                   
                    print(f"quantity: {quantity}, exclude_quantity: {exclude_quantity}")
                    if isinstance(quantity, str):
                        quantity = int(quantity.split("(")[0].strip())
                    rm_needed = rm_quantity * (quantity - exclude_quantity)
                    total_materials[rm_name] = total_materials.get(rm_name, 0) + rm_needed
            else:
                raise ValueError(f"Material {material} not found in materials table.")
        
        return total_materials

    def __set_exclude_text_cell(self, row, quantity):
        cell_colour = DARK_INPUT_CELL if self.dark_mode else LIGHT_INPUT_CELL
        number_item = QTableWidgetItem(str(quantity))  # Default value or you can leave it empty
        number_item.setFlags(number_item.flags() | Qt.ItemIsEditable)  # Make the cell editable
        number_item.setBackground(QColor(cell_colour))
        self.table.setItem(row, EXCLUDE_QUANTITIES_COL_NUM, number_item)      

    def __set_materials_cell(self, row, col, val):
        item = QTableWidgetItem(val)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Make non-editable
        self.table.setItem(row, col, item)

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app_icon = QIcon(resource_path("icon.ico"))
    app.setWindowIcon(app_icon)
    app.setStyle('Fusion')
    window = S2RMFrontend()
    window.show()
    sys.exit(app.exec())

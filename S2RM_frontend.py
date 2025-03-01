import copy
import re
import sys
import os
import json
import math
import sys

import numpy as np

from S2RM_backend import process_material_list

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                               QLabel, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                               QRadioButton, QButtonGroup, QMenuBar, QMenu, QLineEdit, QMessageBox)
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtCore import Qt

from constants import ICE_PER_ICE, SHULKER_BOX_STACK_SIZE, STACK_SIZE, resource_path
# TODO: make helper function for formatting quantities and others used between frontend and backend
from forwardporting import OUTPUT_JSON_VERSION, forwardportJson, get_error_message, format_quantities

# XXX cart storage schem input isnt gfetting sorted

PROGRAM_VERSION = "1.2.0"

DARK_INPUT_CELL = "#111a14"
LIGHT_INPUT_CELL = "#b6e0c4"

TABLE_HEADERS = ["Input", "Quantity", "Exclude", "Raw Material", "Quantity", "Collected", ""]
FILE_LABEL_TEXT = "Select material list file(s):"

# Constants for the table columns
INPUT_ITEMS_COL_NUM = 0
INPUT_QUANTITIES_COL_NUM = INPUT_ITEMS_COL_NUM + 1
EXCLUDE_QUANTITIES_COL_NUM = INPUT_QUANTITIES_COL_NUM + 1
RAW_MATERIALS_COL_NUM = 3
RAW_QUANTITIES_COL_NUM = RAW_MATERIALS_COL_NUM + 1
COLLECTIONS_COL_NUM = 5

class S2RMFrontend(QWidget):
    def __init__(self):
        super().__init__()

        self.output_type = "ingots"
        self.ice_type = "ice"
        
        self.input_items = {}
        self.exclude_text = []
        self.exclude_values = []
        self.collected_data = {}
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
        self.file_button = QPushButton("Browse")
        self.file_button.clicked.connect(self.selectFiles)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_button)
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

        # Item Search Bar
        search_layout = QHBoxLayout()
        self.search_label = QLabel("Raw Material Search:")
        self.search_bar = QLineEdit()
        self.search_bar.textChanged.connect(self.filterAndDisplayMaterials)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_bar)
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
        file_paths, _ = file_dialog.getOpenFileNames(self, "Select Material List Files", litematica_dir,
                                                    "Text/CSV files (*.txt *.csv);;All files (*.*)")
        if file_paths:
            self.file_paths = file_paths
            file_names = ", ".join(os.path.basename(path) for path in file_paths)
            self.file_label.setText(f"{FILE_LABEL_TEXT} {file_names}")

            input_items = {}
            for file_path in file_paths:
                materials_dict = process_material_list(file_path)
                for material, quantity in materials_dict.items():
                    input_items[material] = input_items.get(material, 0) + quantity # Sum dicts
        else:
            return

        self.input_items = dict(sorted(input_items.items(), key=lambda x: (-x[1], x[0])))
        
        # Clear raw materials columns
        self.total_materials = {}
        self.collected_data = {}

        self.displayMaterials()
        self.displayInputMaterials()

    def displayInputMaterials(self):
        input_items_frmtd = copy.deepcopy(self.input_items)
        format_quantities(input_items_frmtd)
        input_items_frmtd = list(input_items_frmtd.items())
        row_count = len(input_items_frmtd)
        
        # Ensure the table has enough rows
        self.table.setRowCount(row_count)
        
        # Determine which quantities to use
        use_exclude_text = len(self.input_items) == len(self.exclude_text)
        
        # Delete data after new input items
        for row in range(row_count, self.table.rowCount()):
            self.__set_materials_cell(row, INPUT_ITEMS_COL_NUM, "")
            self.__set_materials_cell(row, INPUT_QUANTITIES_COL_NUM, "")
            self.table.setCellWidget(row, EXCLUDE_QUANTITIES_COL_NUM, None)
        
        for row, (material, inp_quant) in enumerate(input_items_frmtd):
            # Material name (non-editable)
            material_item = QTableWidgetItem(material)
            material_item.setFlags(material_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, INPUT_ITEMS_COL_NUM, material_item)
            
            # Input quantity (non-editable)
            quantity_item = QTableWidgetItem(str(inp_quant))
            quantity_item.setFlags(quantity_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, INPUT_QUANTITIES_COL_NUM, quantity_item)
            
            # Exclude quantity (editable)
            exclude_text = self.exclude_text[row] if use_exclude_text else 0
            self.__set_exclude_text_cell(row, EXCLUDE_QUANTITIES_COL_NUM, exclude_text)
        
        self.saveInputNumbers()

    def saveInputNumbers(self):
        self.exclude_text = []
        self.exclude_values = []
        for row in range(self.table.rowCount()):
            # Get the value from the third column (number input)
            exclude_cell_text = self.table.item(row, EXCLUDE_QUANTITIES_COL_NUM).text()
            exclude_value = 0
            # Convert the formatted text to a number
            input_quantity = self.table.item(row, INPUT_QUANTITIES_COL_NUM).text()
            required_quantity = int(input_quantity.split("(")[0].strip())
            try:
                exclude_value = clamp(float(exclude_cell_text), 0, required_quantity)
            except ValueError:
                if exclude_cell_text.strip().lower() in ["all", "a"]:
                    exclude_cell_text = "All"
                    exclude_value = required_quantity
                # Check for other valid input formats listing stacks and shulker boxes (e.g., '1s 2sb')
                elif (exclude_value := process_exclude_string(exclude_cell_text)) == -1:
                    # If user enters something proper invalid reset to 0
                    exclude_cell_text = "0"
                    exclude_value = 0
                
                exclude_value = clamp(exclude_value, 0, required_quantity)

            if exclude_value == required_quantity:
                exclude_cell_text = "All"

            self.__set_exclude_text_cell(row, EXCLUDE_QUANTITIES_COL_NUM, exclude_cell_text)
            
            # Add the value to the exclude_text list
            self.exclude_text.append(exclude_cell_text)
            self.exclude_values.append(round(exclude_value))

    def displayMaterials(self, materials=None):
        # Ensure displayed materials still conform to the search term
        if materials is None:
            materials = self.filterMaterials(self.search_bar.text())

        # Deepcopy the materials to avoid modifying the original
        mats_frmtd = copy.deepcopy(materials)
        format_quantities(mats_frmtd)
        self.table.setRowCount(max(self.table.rowCount(), len(mats_frmtd)))
        # delete data in row len(mats_frmtd) to end of table for column 3 and 4
        for row in range(len(mats_frmtd), self.table.rowCount()):
            self.__set_materials_cell(row, RAW_MATERIALS_COL_NUM, "")
            self.__set_materials_cell(row, RAW_QUANTITIES_COL_NUM, "")
            self.table.setCellWidget(row, COLLECTIONS_COL_NUM, None)

        row = 0
        for material, quantity in mats_frmtd.items() if isinstance(mats_frmtd, dict) else mats_frmtd:
            self.__set_materials_cell(row, RAW_MATERIALS_COL_NUM, material)
            self.__set_materials_cell(row, RAW_QUANTITIES_COL_NUM, str(quantity))
            
            # Add checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(self.collected_data.get(material, False))
            checkbox.stateChanged.connect(lambda state, mat=material: self.updateCollected(mat, state))
          
            # Create a widget to center the checkbox
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins

            self.table.setCellWidget(row, COLLECTIONS_COL_NUM, checkbox_widget)

            row += 1

    def processMaterials(self):
        # Ensure exclude input items list is up to date 
        self.saveInputNumbers()

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
            try:
                with open(json_file_path, "r") as f:
                    table_dict = json.load(f)
                    if "input_items" in table_dict and "input_quantities" in table_dict:
                        self.input_items = {item: quantity for item, quantity in
                                            zip(table_dict["input_items"], table_dict["input_quantities"])}
                    else:
                        print("No input items found in JSON file.")
                        return
            except Exception as e:
                print(f"An error occurred: {e}")
                return
            
            self.file_paths = json_file_path

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
        self.displayMaterials()
        self.displayInputMaterials()

    def filterAndDisplayMaterials(self, search_term):
        materials = self.filterMaterials(search_term)
        self.displayInputMaterials()
        self.displayMaterials(materials)

    def filterMaterials(self, search_term):
        filtered_materials = {}
        if hasattr(self, "total_materials"):
            for material, quantity in self.total_materials.items():
                if search_term.lower() in material.lower():
                    filtered_materials[material] = quantity
        
        return filtered_materials

    def saveJson(self):
        """Save object data to a JSON-compatible dictionary."""
        # Ensure input numbers are saved
        self.saveInputNumbers()
        
        table_dict = {}
        table_dict["version"] = OUTPUT_JSON_VERSION
        
        # Add attributes in specific order with appropriate defaults
        self.__add_with_default(table_dict, "file_paths", "material_list_paths", [])
        self.__add_with_default(table_dict, "output_type", "output_type", "")
        self.__add_with_default(table_dict, "ice_type", "ice_type", "")
        
        if hasattr(self, "input_items"):
            table_dict["input_items"] = list(self.input_items.keys())
            table_dict["input_quantities"] = list(self.input_items.values())
        else:
            table_dict["input_items"], table_dict["input_quantities"] = [], []
        
        self.__add_with_default(table_dict, "exclude_text", "exclude_text", [])
        self.__add_with_default(table_dict, "exclude_values", "exclude_values", [])
        
        if hasattr(self, "total_materials"):
            table_dict["raw_materials"] = list(self.total_materials.keys())
            table_dict["raw_quantities"] = list(self.total_materials.values())
        else:
            table_dict["raw_materials"], table_dict["raw_quantities"] = [], []
        
        self.__add_with_default(table_dict, "collected_data", "collected", {})

        # Save the JSON file to the desktop or elsewhere
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self, "Save JSON File",os.path.join(desktop_path, "raw_materials.json"),
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
        file_path, _ = file_dialog.getOpenFileName(
            self, "Open JSON File", desktop_path, "JSON files (*.json);;All files (*.*)"
        )
        if file_path:
            with open(file_path, "r") as f:
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

            print(f"JSON opened successfully from: {file_path}")

            # Reset the table
            self.table.setRowCount(0)
            self.file_paths = []
            self.input_items = {}
            self.exclude_text = []
            self.exclude_values = []
            self.total_materials = {}
            self.collected_data = {}
            
            if "output_type" in table_dict:
                self.output_type = table_dict["output_type"]
                self.__set_radio_button(self.output_type, ["blocks", "ingots"],
                                        [self.blocks_radio, self.ingots_radio])
            if "ice_type" in table_dict:
                self.ice_type = table_dict["ice_type"]
                self.__set_radio_button(self.ice_type, ["freeze", "ice"],
                                        [self.packed_ice_radio, self.ice_radio])

            if "material_list_paths" in table_dict:
                self.file_paths = table_dict["material_list_paths"]

            if "input_items" in table_dict and "input_quantities" in table_dict:
                input_items = {item: quantity for item, quantity in 
                                    zip(table_dict["input_items"], table_dict["input_quantities"])}
                
                # Make sure it's sorted
                self.input_items = dict(sorted(input_items.items(), key=lambda x: (-x[1], x[0])))

            if "exclude_text" in table_dict:
                self.exclude_text = table_dict["exclude_text"]
            
            if "exclude_values" in table_dict:
                self.exclude_values = np.round(table_dict["exclude_values"]).tolist()

            if "raw_materials" in table_dict and "raw_quantities" in table_dict:
                total_materials = {material: quantity for material, quantity in
                                        zip(table_dict["raw_materials"], table_dict["raw_quantities"])}
                
                # Make sure it's sorted
                self.total_materials = dict(sorted(total_materials.items(), key=lambda x: (-x[1], x[0])))

            if "collected" in table_dict:
                self.collected_data = table_dict["collected"]

            self.displayInputMaterials()
            self.displayMaterials(self.total_materials)
            self.file_paths = file_path
            self.file_label.setText(f"{FILE_LABEL_TEXT} {os.path.basename(file_path)}")
        else:
            print("No file selected")

    def exportCSV(self):
        """Export the current table to a CSV file."""
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
                    headers = [self.table.horizontalHeaderItem(col).text()
                               if self.table.horizontalHeaderItem(col) 
                               else f"Column {col+1}" 
                               for col in range(self.table.columnCount())]
                    f.write(",".join(headers) + "\n")
                    
                    # Write table contents
                    for row in range(self.table.rowCount()):
                        for col in range(self.table.columnCount() - 1):
                            item = self.table.item(row, col)
                            if item:
                                # Remove alt quantity amount with stacks and shulker boxes
                                if col in [EXCLUDE_QUANTITIES_COL_NUM, RAW_QUANTITIES_COL_NUM]:
                                    quantity = item.text().split("(")[0].strip()
                                    f.write(quantity)
                                else:
                                    f.write(item.text())
                            # If not item, check if it's in the collected column
                            elif col == COLLECTIONS_COL_NUM:
                                widget = self.table.cellWidget(row, COLLECTIONS_COL_NUM)
                                if widget:
                                    checkbox = widget.layout().itemAt(0).widget()
                                    f.write(str(checkbox.isChecked()))
                            f.write(",")
                        f.write("\n")
                print(f"CSV saved successfully to: {file_path}")
            except Exception as e:
                print(f"Error saving CSV: {e}")

    def clearMaterials(self):
        self.table.setRowCount(0) # Clear the table
        if hasattr(self, "total_materials"):
            self.total_materials = {}
        if hasattr(self, "input_items"):
            self.input_items = {}
        if hasattr(self, "exclude_text"):
            self.exclude_text = []
        if hasattr(self, "exclude_values"):
            self.exclude_values = []
        
        self.file_paths = []
        self.file_label.setText(FILE_LABEL_TEXT)
        self.collected_data.clear()

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
        self.file_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.process_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.save_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.open_json_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.clear_button.setStyleSheet("QPushButton { background-color: #353535; color: white; }")
        self.search_bar.setStyleSheet("QLineEdit { background-color: #191919; color: white; }")
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
        self.file_button.setStyleSheet("")
        self.process_button.setStyleSheet("")
        self.save_button.setStyleSheet("")
        self.open_json_button.setStyleSheet("")
        self.clear_button.setStyleSheet("")
        self.search_bar.setStyleSheet("")
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
                                                   
                    rm_needed = rm_quantity * (quantity - exclude_quantity)
                    total_materials[rm_name] = total_materials.get(rm_name, 0) + rm_needed
            else:
                raise ValueError(f"Material {material} not found in materials table.")
        
        return total_materials

    def __set_exclude_text_cell(self, row, col, quantity):
        cell_colour = DARK_INPUT_CELL if self.dark_mode else LIGHT_INPUT_CELL
        number_item = QTableWidgetItem(str(quantity))  # Default value or you can leave it empty
        number_item.setFlags(number_item.flags() | Qt.ItemIsEditable)  # Make the cell editable
        number_item.setBackground(QColor(cell_colour))
        self.table.setItem(row, col, number_item)      

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

def condense_material(processed_materials: dict, material: str, quantity: float) -> None:
    if re.match(r'\w+_ingot$', material):
        block_name = material.replace("_ingot", "_block")
        add_resources(processed_materials, material, block_name, quantity)
    elif re.match(r'(diamond|redstone|coal|lapis_lazuli|emerald)$', material):
        block_name = f"{material}_block"
        add_resources(processed_materials, material, block_name, quantity)
    elif material == 'slime_ball':
        block_name = 'slime_block'
        add_resources(processed_materials, material, block_name, quantity)
    elif material == 'wheat':
        block_name = 'hay_block'
        add_resources(processed_materials, material, block_name, quantity)
    elif material == 'snowball':
        block_name = 'snow_block'
        add_resources(processed_materials, material, block_name, quantity, compact_num=4)
    elif material == 'bone_meal':
        block_name = 'bone_block'
        add_resources(processed_materials, material, block_name, quantity)
    else:
        processed_materials[material] = quantity

def add_resources(processed_materials: dict, material: str, block_name: str, quantity: float,
                  compact_num: int = 9) -> None:
    blocks_needed = int(quantity // compact_num)
    remaining_ingots = quantity - (blocks_needed * compact_num)

    if blocks_needed > 0:
        processed_materials[block_name] = processed_materials.get(block_name, 0) + blocks_needed
    if remaining_ingots > 0:
        processed_materials[material] = processed_materials.get(material, 0) + remaining_ingots
    
    if remaining_ingots > compact_num:
        raise ValueError(f"Error: {material} has more than {compact_num} remaining ingots.")

def process_exclude_string(input_string):
    """
    Processes the input string according to the given rules:

    1.  Extracts digits from the string.
    2.  Multiplies each digit by 64 if followed by 's', and by 64*27 if followed by 'sb'.
    3.  Calculates the sum of the multiplied digits.
    4.  Handles cases where the text following the digit is 's' or 'sb' (case-insensitive).

    Args:
        input_string: The input string to process.

    Returns:
        The sum of the multiplied digits.
    """

    if not input_string:
        return -1
    
    # Check if input matches the allowed characters pattern, not fully exhaustive e.g.
    # 'sb1' should be invalid but it isn't so don't go crazy with this
    if not re.fullmatch(r'(\d|\s|s|sb)+', input_string, re.IGNORECASE):
        return -1

    # Check for invalid combinations (e.g., 'ss', 'sss', etc.)
    if 'ss' in input_string or 'sss' in input_string:
        return -1
    
    total = 0
    matches = re.finditer(r"(\d)(sb|s)?", input_string, re.IGNORECASE)

    for match in matches:
        digit = int(match.group(1))
        suffix = match.group(2)

        if suffix:
            if suffix.lower() == 's':
                total += digit * STACK_SIZE
            elif suffix.lower() == 'sb':
                total += digit * SHULKER_BOX_STACK_SIZE
        else:
            total += digit

    return total

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app_icon = QIcon(resource_path("icon/icon.ico"))
    app.setWindowIcon(app_icon)
    app.setStyle('Fusion')
    window = S2RMFrontend()
    window.show()
    sys.exit(app.exec())

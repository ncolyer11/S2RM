import copy
import re
import sys
import os
import json
import math

import numpy as np

from S2RM_backend import process_material_list

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                               QLabel, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                               QRadioButton, QButtonGroup, QMenuBar, QMenu, QLineEdit, QMessageBox)
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtCore import Qt

from constants import ICE_PER_ICE, SHULKER_BOX_STACK_SIZE, STACK_SIZE, resource_path


PROGRAM_VERSION = "1.1.1"
OUTPUT_JSON_VERSION = 3 # Manually track the version of the output json files for compatibility

DARK_INPUT_CELL = "#111a14"
LIGHT_INPUT_CELL = "#b6e0c4"

class S2RMFrontend(QWidget):
    def __init__(self):
        super().__init__()

        self.output_type = "ingots"
        self.ice_type = "ice"
        
        self.input_items = {}
        self.exclude_items = []
        self.collected_data = {}
        self.dark_mode = True

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Menu Bar
        self.menu_bar = QMenuBar()  # Store the menu bar as an instance variable
        self.file_menu = QMenu("File", self)  # Store file_menu
        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
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
        self.file_label = QLabel("Select Material List File:")
        self.file_button = QPushButton("Browse")
        self.file_button.clicked.connect(self.selectFile)
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
        self.search_label = QLabel("Search:")
        self.search_bar = QLineEdit()
        self.search_bar.textChanged.connect(self.filterAndDisplayMaterials)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_bar)
        layout.addLayout(search_layout)
    
        # Table Display
        self.table = QTableWidget()
        headers = ["Input", "Quantity", "Exclude", "Raw Material", "Quantity", "Collected", ""]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        layout.addWidget(self.table)
        self.table.setColumnWidth(0, 210)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(4, 200)
        self.table.setColumnWidth(5, 80)
        
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

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

    def selectFile(self):
        litematica_dir = self.get_litematica_dir()
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Material List File", litematica_dir, "Text files (*.txt);;All files (*.*)")
        if file_path:
            self.file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
            materials_dict = process_material_list(self.file_path)
            # Set column 0 of self.table to the keys of materials_dict, and column 1 to checkboxes enabled to true
            self.input_items = materials_dict
            self.displayInputMaterials()

    def displayInputMaterials(self):
        input_items = list(self.input_items.items())
        row_count = len(input_items)
        
        # Ensure the table has enough rows
        self.table.setRowCount(max(self.table.rowCount(), row_count))
        
        # Determine which quantities to use
        use_exclude_items = len(self.input_items) == len(self.exclude_items)
        
        for row, (material, inp_quant) in enumerate(input_items):
            # Column 0: Material name (non-editable)
            material_item = QTableWidgetItem(material)
            material_item.setFlags(material_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, material_item)
            
            # Column 1: Input quantity (non-editable)
            quantity_item = QTableWidgetItem(str(inp_quant))
            quantity_item.setFlags(quantity_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, quantity_item)
            
            # Column 2: exclude quantity (editable)
            exc_quant = self.exclude_items[row] if use_exclude_items else 0
            self.__set_exclude_input_cell(row, 2, exc_quant)
        
        self.saveInputNumbers()

    def saveInputNumbers(self):
        self.exclude_items = []  # Initialize or reset the list
        for row in range(self.table.rowCount()):
            # Get the value from the third column (number input)
            number_value = self.table.item(row, 2).text()
            required_quantity = float(self.table.item(row, 1).text())
            
            try:
                number_value = clamp(float(number_value), 0, required_quantity)
            except ValueError:
                if number_value.strip().lower() in ["all", "a"]:  # Allow 'all' or 'a' to represent the full quantity
                    number_value = required_quantity
                # Check for other valid input formats listing stacks and shulker boxes (e.g., '1s 2sb')
                elif (number_value := process_exclude_string(number_value)) == -1:
                    # If user enters something proper invalid reset to 0
                    number_value = 0
                
                number_value = clamp(number_value, 0, required_quantity)
                self.__set_exclude_input_cell(row, 2, number_value)
            
            # Add the value to the exclude_items list
            self.exclude_items.append(round(number_value))

    def processMaterials(self):
        # Ensure exclude input items list is up to date 
        self.saveInputNumbers()

        if not hasattr(self, "file_path"):
            return

        raw_materials_table_path = resource_path("raw_materials_table.json")
        with open(raw_materials_table_path, "r") as f:
            materials_table = json.load(f)
        # If the file path is a .txt file, use it directly
        if self.file_path.endswith("txt"):
            total_materials = self.__get_total_mats_from_txt(self.file_path, materials_table)
        # Otherwise, if the file path is a .json file, extract the litematica_mats_list_path
        elif self.file_path.endswith("json"):
            with open(self.file_path, "r") as f:
                table_dict = json.load(f)
                if "input_items" in table_dict and "input_quantities" in table_dict:
                    self.input_items = {item: quantity for item, quantity in
                                        zip(table_dict["input_items"], table_dict["input_quantities"])}
                    total_materials = self.__get_total_mats_from_input(materials_table)
                else:
                    print("No input items found in JSON file.")
                    return
        else:
            raise ValueError(f"Invalid file type: {self.file_path}")

        # Round final quantities up
        for material, quantity in total_materials.items():
            total_materials[material] = math.ceil(quantity)

        # Post-process to handle blocks and remaining ingots
        if self.output_type == "blocks":
            processed_materials = {}
            # Run 2 passes to handle blocks turning into ingots before an ingot can be compacted
            for material, quantity in total_materials.items():
                condense_material(processed_materials, material, quantity)

            total_materials = processed_materials
            
        # Convert to dict and sort by quantity (descending) then by material name (ascending)
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

    def displayMaterials(self, materials=None):
        # Ensure displayed materials still conform to the search term
        if materials is None:
            materials = self.filterMaterials(self.search_bar.text())

        # Deepcopy the materials to avoid modifying the original
        mats_frmtd = copy.deepcopy(materials)
        self.__format_quantities(mats_frmtd)
        self.table.setRowCount(max(self.table.rowCount(), len(mats_frmtd)))
        # delete data in row len(mats_frmtd) to end of table for column 3 and 4
        for row in range(len(mats_frmtd), self.table.rowCount()):
            self.__set_raw_materials_cell(row, 3, "")
            self.__set_raw_materials_cell(row, 4, "")
            self.table.setCellWidget(row, 5, None)

        row = 0
        for material, quantity in mats_frmtd.items() if isinstance(mats_frmtd, dict) else mats_frmtd:
            self.__set_raw_materials_cell(row, 3, material)
            self.__set_raw_materials_cell(row, 4, str(quantity))
            
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

            self.table.setCellWidget(row, 5, checkbox_widget)

            row += 1

    def saveJson(self):
        # Simplify things by making each column a key
        table_dict = {}
        self.saveInputNumbers()
        
        table_dict["version"] = OUTPUT_JSON_VERSION
        
        if hasattr(self, "file_path"):
            table_dict["litematica_mats_list_path"] = self.file_path

        if hasattr(self, "input_items"):
            table_dict["input_items"] = list(self.input_items.keys()) 
            table_dict["input_quantities"] = list(self.input_items.values())

        if hasattr(self, "exclude_items"):
            table_dict["exclude_input"] = self.exclude_items

        if hasattr(self, "total_materials"):
            table_dict["raw_materials"] = list(self.total_materials.keys())
            table_dict["raw_quantities"] = list(self.total_materials.values())

        if hasattr(self, "collected_data"):
            table_dict["collected"] = self.collected_data

        # If there's nothing to save, return early
        if not table_dict:
            print("No data to save.")
            return

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

                if "version" not in table_dict or table_dict["version"] != OUTPUT_JSON_VERSION:
                    if "version" not in table_dict:
                        version = "not specified"
                    else:
                        version = table_dict["version"]

                    message = (
                        "Warning: The materials table you are trying to open is uses an incompatible format.\n\n"
                        f"Expected version: '{OUTPUT_JSON_VERSION}'.\nFound Version: '{version}'.\n\n"
                        "Backporting is not currently supported.\n"
                        "Therefore, the selected materials table cannot be opened."
                    )
                    QMessageBox.warning(
                        self,
                        "Incompatible Materials Table",
                        message,
                    )
                    return

            print(f"JSON opened successfully from: {file_path}")

            # Reset the table
            self.table.setRowCount(0)
            self.file_path = ""
            self.input_items = {}
            self.exclude_items = []
            self.total_materials = {}
            self.collected_data = {}

            if "litematica_mats_list_path" in table_dict:
                self.file_path = table_dict["litematica_mats_list_path"]

            if "input_items" in table_dict:
                self.input_items = {item: quantity for item, quantity in 
                                    zip(table_dict["input_items"], table_dict["input_quantities"])}

            if "exclude_input" in table_dict:
                self.exclude_items = np.round(table_dict["exclude_input"]).tolist()

            if "raw_materials" in table_dict:
                self.total_materials = {material: quantity for material, quantity in
                                        zip(table_dict["raw_materials"], table_dict["raw_quantities"])}

            if "collected" in table_dict:
                self.collected_data = table_dict["collected"]

            self.displayInputMaterials()
            self.displayMaterials(self.total_materials)
            self.file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
        else:
            print("No file selected")

    def clearMaterials(self):
        self.table.setRowCount(0) # Clear the table
        if hasattr(self, "total_materials"):
            del self.total_materials
        if hasattr(self, "input_items"):
            del self.input_items
        if hasattr(self, "exclude_items"):
            del self.exclude_items
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
        
        self.setEditableCellStyles(LIGHT_INPUT_CELL)  # Light mode cell color

        # Reset credits and source text color
        self.updateCreditsLabel()
    
    def setEditableCellStyles(self, hex_color):
        """Sets background color for editable cells."""
        for row in range(self.table.rowCount()):
            # Assuming the editable column is the 3rd column (index 2)
            number_item = self.table.item(row, 2)
            if number_item and number_item.flags() & Qt.ItemIsEditable:
                number_item.setBackground(QColor(hex_color))

    def updateCreditsLabel(self):
        # Choose colors based on mode
        if self.dark_mode:
            link_color = "#ADD8E6"  # Light blue for dark mode
            version_color = "#FFD700"  # Gold for dark mode
        else:
            link_color = "#0066CC"  # More pleasant dark blue for light mode
            version_color = "#FF4500"  # Slightly darker orange for light mode
        
        # Set the text with inline styling for the links
        non_breaking_spaces = "&nbsp;" * 10
        self.credits_and_source_label.setText(
            f'<a style="color: {link_color};" '
            f'href="https://youtube.com/ncolyer">Made by ncolyer</a> | '
            f'<span style="color: {version_color};">Version: {PROGRAM_VERSION}</span> | '
            f'<a style="color: {link_color};" '
            f'href="https://github.com/ncolyer11/S2RM">Source</a>{non_breaking_spaces}'
        )

    def __get_total_mats_from_txt(self, file_path, materials_table) -> dict:
        self.input_items = process_material_list(file_path)
        return self.__get_total_mats_from_input(materials_table)

    def __get_total_mats_from_input(self, materials_table) -> dict:
        total_materials = {}
        for input_item_idx, (material, quantity) in enumerate(self.input_items.items()):
            if material in materials_table:
                exclude_quantity = self.exclude_items[input_item_idx]
                for raw_material in materials_table[material]:
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
    
    def __format_quantities(self, total_materials):
        for material, quantity in total_materials.items():
            if quantity >= SHULKER_BOX_STACK_SIZE:
                num_shulker_boxes = quantity // SHULKER_BOX_STACK_SIZE
                remaining_stacks = (quantity % SHULKER_BOX_STACK_SIZE) // STACK_SIZE
                remaining_items = quantity % STACK_SIZE
                total_materials[material] = f"{quantity} ({num_shulker_boxes} SB + {remaining_stacks} stacks + {remaining_items})"
            elif quantity >= STACK_SIZE:
                num_stacks = quantity // STACK_SIZE
                remaining_items = quantity % STACK_SIZE
                total_materials[material] = f"{quantity} ({num_stacks} stacks + {remaining_items})"
            else:
                total_materials[material] = str(quantity)
        
    def __set_exclude_input_cell(self, row, col, quantity):
        cell_colour = DARK_INPUT_CELL if self.dark_mode else LIGHT_INPUT_CELL
        number_item = QTableWidgetItem(str(quantity))  # Default value or you can leave it empty
        number_item.setFlags(number_item.flags() | Qt.ItemIsEditable)  # Make the cell editable
        number_item.setBackground(QColor(cell_colour))
        self.table.setItem(row, col, number_item)      

    def __set_raw_materials_cell(self, row, col, val):
        item = QTableWidgetItem(val)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Make non-editable
        self.table.setItem(row, col, item)

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
                total += digit * 64
            elif suffix.lower() == 'sb':
                total += digit * 64 * 27
        else:
            total += digit

    return total

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app_icon = QIcon(resource_path("icon/icon.ico"))
    app.setWindowIcon(app_icon)
    window = S2RMFrontend()
    window.show()
    sys.exit(app.exec())

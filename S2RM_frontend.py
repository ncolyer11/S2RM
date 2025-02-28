import re
import sys
import os
import json
import math

from S2RM_backend import process_material_list

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                               QRadioButton, QButtonGroup, QMenuBar, QMenu, QLineEdit)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from constants import SHULKER_BOX_STACK_SIZE, STACK_SIZE

# XXX go through mats list on debug file to see what else can be compacted

class S2RMFrontend(QWidget):
    def __init__(self):
        super().__init__()

        self.output_type = "ingots"
        self.ice_type = "ice"

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Menu Bar
        menu_bar = QMenuBar()
        file_menu = QMenu("File", self)
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        menu_bar.addMenu(file_menu)
        layout.addWidget(menu_bar)

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
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Material", "Quantity"])
        layout.addWidget(self.table)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 200)

        self.setLayout(layout)
        self.setWindowTitle("S2RM: Schematic to Raw Materials")
        self.setGeometry(300, 300, 800, 600)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        credits_and_source_label = QLabel('<a href="https://youtube.com/ncolyer">Made by ncolyer</a> | <a href="https://github.com/ncolyer11/S2RM">Source</a>')
        credits_and_source_label.setAlignment(Qt.AlignCenter)
        credits_and_source_label.setOpenExternalLinks(True)
        layout.addWidget(credits_and_source_label)

    def processMaterials(self):
        if not hasattr(self, "file_path"):
            return

        if self.file_path.endswith("txt"):
            materials_dict = process_material_list(self.file_path)
            with open("raw_materials_table.json", "r") as f:
                materials_table = json.load(f)
            total_materials = self.__get_total_mats_from_txt(materials_dict, materials_table)
            
        elif self.file_path.endswith("json"):
            with open(self.file_path, "r") as f:
                total_materials = json.load(f)
            
            
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

    def filterAndDisplayMaterials(self, search_term):
        materials = self.filterMaterials(search_term)
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
        self.__format_quantities(materials)
        self.table.setRowCount(len(materials))
        row = 0
        for material, quantity in materials.items() if isinstance(materials, dict) else materials:
            self.table.setItem(row, 0, QTableWidgetItem(material))
            self.table.setItem(row, 1, QTableWidgetItem(str(quantity)))
            row += 1

    def saveJson(self):
        if hasattr(self, "total_materials"):
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getSaveFileName(self, "Save JSON File", os.path.join(desktop_path, "raw_materials.json"), "JSON files (*.json);;All files (*.*)")
            if file_path:
                try:
                    with open(file_path, "w") as f:
                        json.dump(self.total_materials, f, indent=4)
                    print(f"JSON saved successfully to: {file_path}")
                except Exception as e:
                    print(f"Error saving JSON: {e}")
        else:
            print("No materials to save.")

    def openJson(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Open JSON File", "", "JSON files (*.json);;All files (*.*)")
        if file_path:
            with open(file_path, "r") as f:
                data = json.load(f)
            # Check the json is "material": quantity format, just check the first
            if not all(isinstance(k, str) and isinstance(v, int) for k, v in data.items()):
                raise ValueError("JSON file must be in the format: {\"material\": quantity}.\n"
                                 f"Found: {next(iter(data.items()))}")
     
            self.displayMaterials(data)
            self.total_materials = data # Store the loaded data
            self.file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
                
    def clearMaterials(self):
        self.table.setRowCount(0)  # Clear the table
        if hasattr(self, "total_materials"):
            del self.total_materials  # Remove the total_materials attribute

######### Helper and Private Methods #########

    def __get_total_mats_from_txt(self, materials_dict, materials_table) -> dict:
        total_materials = {}
        for material, quantity in materials_dict.items():
            if material in materials_table:
                for raw_material in materials_table[material]:
                    rm_name, rm_quantity = raw_material["item"], raw_material["quantity"]

                    # Keep or 'freeze' the original ice type if specified
                    if self.ice_type == "freeze":
                        if material == "packed_ice":
                            rm_name = "packed_ice"
                            rm_quantity = rm_quantity / 9
                        elif material == "blue_ice":
                            rm_name = "blue_ice"
                            rm_quantity = rm_quantity / 81
                                                   
                    rm_needed = rm_quantity * quantity
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
                

    def selectFile(self):
        litematica_dir = self.get_litematica_dir()
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Material List File", litematica_dir, "Text files (*.txt);;All files (*.*)")
        if file_path:
            self.file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")

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
        return ""  # Return an empty string if directory not found

    def updateOutputType(self):
        self.output_type = "ingots" if self.ingots_radio.isChecked() else "blocks"
            
    def updateIceType(self):
        self.ice_type = "ice" if self.ice_radio.isChecked() else "freeze"

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app_icon = QIcon("icon.ico")
    app.setWindowIcon(app_icon)
    window = S2RMFrontend()
    window.show()
    sys.exit(app.exec())
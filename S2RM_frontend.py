import re
import sys
import os
import json
import math

from S2RM_backend import process_material_list

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
                               QLabel, QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
                               QRadioButton, QButtonGroup, QMenuBar, QMenu, QLineEdit)
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtCore import Qt

from constants import SHULKER_BOX_STACK_SIZE, STACK_SIZE

# XXX go through mats list on debug file to see what else can be compacted

class S2RMFrontend(QWidget):
    def __init__(self):
        super().__init__()

        self.output_type = "ingots"
        self.ice_type = "ice"
        
        self.collected_data = {}
        self.dark_mode = False

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Menu Bar
        self.menu_bar = QMenuBar()  # Store the menu bar as an instance variable
        self.file_menu = QMenu("File", self)  # Store file_menu
        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        self.menu_bar.addMenu(self.file_menu)

        self.view_menu = QMenu("View", self)  # Store view_menu
        dark_mode_action = self.view_menu.addAction("Dark Mode")
        dark_mode_action.setCheckable(True)
        dark_mode_action.triggered.connect(self.toggleDarkMode)
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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Material", "Quantity", "Collected", ""])
        layout.addWidget(self.table)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 80)
        
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        self.setLayout(layout)
        self.setWindowTitle("S2RM: Schematic to Raw Materials")
        self.setGeometry(300, 300, 800, 600)
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.credits_and_source_label = QLabel()
        self.credits_and_source_label.setAlignment(Qt.AlignCenter)
        self.credits_and_source_label.setOpenExternalLinks(True)
        layout.addWidget(self.credits_and_source_label)
        
        self.updateCreditsLabel()

    def toggleDarkMode(self, checked):
        self.dark_mode = checked
        if self.dark_mode:
            self.setDarkMode()
        else:
            self.setLightMode()

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

            self.table.setCellWidget(row, 2, checkbox_widget)

            row += 1

    def saveJson(self):
        if hasattr(self, "total_materials"):
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getSaveFileName(
                self, "Save JSON File",os.path.join(desktop_path, "raw_materials.json"),
                "JSON files (*.json);;All files (*.*)"
            )
            print(self.collected_data)
            if file_path:
                try:
                    save_data = {"materials": self.total_materials, "collected": self.collected_data}
                    with open(file_path, "w") as f:
                        json.dump(save_data, f, indent=4)
                    print(f"JSON saved successfully to: {file_path}")
                except Exception as e:
                    print(f"Error saving JSON: {e}")
        else:
            print("No materials to save.")

    def openJson(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Open JSON File", "", "JSON files (*.json);;All files (*.*)"
        )
        if file_path:
            with open(file_path, "r") as f:
                data = json.load(f)

            materials = data.get("materials", {})
            self.collected_data = data.get("collected", {})

            if not all(isinstance(k, str) and isinstance(v, int) for k, v in materials.items()):
                raise ValueError("JSON file must be in the format: {\"material\": quantity} for materials.\n"
                                 f"Found: {next(iter(materials.items()))}")

            self.displayMaterials(materials)
            self.total_materials = materials  # Store the loaded data
            self.file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")

    def clearMaterials(self):
        self.table.setRowCount(0)  # Clear the table
        if hasattr(self, "total_materials"):
            del self.total_materials  # Remove the total_materials attribute
        self.collected_data.clear() # clear collected data.

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
    
    def updateCollected(self, material, state):
        self.collected_data[material] = Qt.CheckState(state) == Qt.CheckState.Checked

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

        # Reset credits and source text color
        self.updateCreditsLabel()

    def updateCreditsLabel(self):
        # Choose colors based on mode
        if self.dark_mode:
            link_color = "#ADD8E6"  # Light blue for dark mode
        else:
            link_color = "#0066CC"  # More pleasant dark blue for light mode
        
        # Set the text with inline styling for the links
        self.credits_and_source_label.setText(
            f'<a style="color: {link_color};" '
            f'href="https://youtube.com/ncolyer">Made by ncolyer</a> | '
            f'<a style="color: {link_color};" '
            f'href="https://github.com/ncolyer11/S2RM">Source</a>'
        )

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

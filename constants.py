import json
import os
import sys

ICE_PER_ICE = 9
DF_STACK_SIZE = 64
SHULKER_BOX_SIZE = 27
DF_SHULKER_BOX_STACK_SIZE = DF_STACK_SIZE * SHULKER_BOX_SIZE

NODE_COLOUR = '#102d5c'

IGNORE_ITEMS_REGEX = r'(dye_\w+_(bed|carpet))|bundle'
AXIOM_MATERIALS_REGEX = r"""
    (stone|cobblestone|\w+_ingot$|slime_ball|redstone|\w+smithing_template|bone_meal|
    wheat|quartz|resin_clump|coal|diamond|dried_kelp|emerald|honey_bottle|lapis_lazuli|white_wool|
    raw_\w+(?!_block)|\w+dye|leather)$
"""

# Convert a tagged material category to its cheapest base material
TAGGED_MATERIALS_BASE = {
    # Logs and wood-related materials
    "#logs": "oak_log",
    "#logs_that_burn": "oak_log",
    "#oak_logs": "oak_log",
    "#birch_logs": "birch_log",
    "#spruce_logs": "spruce_log",
    "#jungle_logs": "jungle_log",
    "#acacia_logs": "acacia_log",
    "#dark_oak_logs": "dark_oak_log",
    "#pale_oak_logs": "pale_oak_log",
    "#cherry_logs": "cherry_log",
    "#mangrove_logs": "mangrove_log",
    "#warped_stems": "warped_stem",
    "#crimson_stems": "crimson_stem",
    "#bamboo_blocks": "bamboo_block",
    "#planks": "oak_planks",
    "#wooden_slabs": "oak_slab",
    
    # Tool and crafting materials
    "#wooden_tool_materials": "oak_planks",
    "#stone_tool_materials": "cobblestone",
    "#iron_tool_materials": "iron_ingot",
    "#diamond_tool_materials": "diamond",
    "#gold_tool_materials": "gold_ingot",
    "#stone_crafting_materials": "cobblestone",
    
    # Fuels and smelting-related materials
    "#coals": "coal",
    "#soul_fire_base_blocks": "soul_sand",
    "#smelts_to_glass": "sand",
    
    # Miscellaneous materials
    "#leaves": "oak_leaves",
    "#eggs": "egg",
    "#wool": "white_wool",
}

ITEM_TAGS = {
    # Internally used shorthands for various items
    "redstone_comparator": "comparator",
    "redstone_repeater": "repeater",
    "redstone_dust": "redstone",
    "lapis_lazuli_block": "lapis_block",
    "deepslate_lapis_lazuli_ore": "deepslate_lapis_ore",
    "lapis_lazuli_ore": "lapis_ore",
    "smooth_quartz_block": "smooth_quartz",
    "jack_o'lantern": "jack_o_lantern",
    "vines": "vine",
    "hay_bale": "hay_block",
    "monster_spawner": "spawner",
    "jigsaw_block": "jigsaw",
    
    # UK Translations
    "compressed_ice": "packed_ice",
    "biscuit": "cookie",
    
    # Canadian Translations
    "beet_seeds": "beetroot_seeds",
    "moon_daisy": "oxeye_daisy",
    
    # NZ Translations
    "watermelon": "melon",
    "watermelon_seeds": "melon_seeds",
    "ender_dragon_head": "dragon_head",
}

# Skip these blocks when calculating materials
INVALID_BLOCKS = [
    "air",
    "void_air",
    "cave_air",
    "fire",
    "soul_fire",
    "nether_portal",
    "end_portal",
    "piston_head", # yes you can have a piston head on its own, but it's rare and you can get the piston back anyways if you're skilled enough
]

# Convert a block name to an item name
BLOCK_TAGS = {
    "redstone_wire": "redstone",
    "tripwire": "string",
    "carrots": "carrot",
    "potatoes": "potato",
    "cocoa": "cocoa_beans",
    "water": "water_bucket",
    "lava": "lava_bucket",
    "powder_snow": "powder_snow_bucket",
    "bubble_column": "water_bucket",
    "pumpkin_stem": "pumpkin_seeds",
    "melon_stem": "melon_seeds",
    "bamboo_sapling": "bamboo",
    "beetroots": "beetroot",
    "big_dripleaf_stem": "big_dripleaf",
    "small_dripleaf_stem": "small_dripleaf",
    "kelp_plant": "kelp",
    "pitcher_crop": "pitcher_pod",
    "sweet_berry_bush": "sweet_berries",
    "torchflower_crop": "torchflower_seeds",
    "tall_seagrass": "seagrass",
    "azalea_bush": "azalea",
    "flowering_azalea_bush": "flowering_azalea",
    "cave_vines": "vine",
    "cave_vines_plant": "vine",
    "moving_piston": "block36"
}

# Entities that have the same name as their item form
SIMPLE_ENTITIES = [
    "item_frame",
    "painting",
    "armor_stand",
]

# To get this to build to .exe we need this code, but to avoid circular dependencies it needs to be here, kinda eh
def constants_py_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Load a dictionary containing all items that don't stack to 64, and their stack size (either 16 or 1)
with open(constants_py_resource_path("data/116_stacks.json"), "r") as f:
    LIMITED_STACK_ITEMS = json.load(f)

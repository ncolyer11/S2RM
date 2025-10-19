import os

PROGRAM_VERSION = "1.3.5"
OUTPUT_JSON_VERSION = 8 # Track the version of the output json files for forwardporting capability

S2RM_API_RELEASES_URL = "https://api.github.com/repos/ncolyer11/S2RM/releases/latest"
S2RM_RELEASES_URL = "https://github.com/ncolyer11/S2RM/releases/latest"
# File related constants
DATA_DIR = "data"
GAME_DATA_DIR = "data/game"
MC_DOWNLOADS_DIR = "mc_downloads"
CONFIG_PATH = "src/config.json"
ICON_PATH = "src/icon.ico"

BACKUP_VERSION = "1.21.5" # The latest version that I know this program's parsing works with
ITEMS_JSON = "items.json"
BLOCKS_JSON = "blocks.json"
ENTITIES_JSON = "entities.json"
LIMTED_STACKS_NAME = "limited_stack_items.json"
RAW_MATS_TABLE_NAME = "raw_materials_table.json"
GAME_DATA_FILES = [BLOCKS_JSON, ITEMS_JSON, ENTITIES_JSON]

ICE_PER_ICE = 9
DF_STACK_SIZE = 64
SHULKER_BOX_SIZE = 27
DF_SHULKER_BOX_STACK_SIZE = DF_STACK_SIZE * SHULKER_BOX_SIZE

NODE_COLOUR = '#102d5c'

IGNORE_ITEMS_REGEX = r'dye_\w+_(bed|carpet)'
AXIOM_MATERIALS_REGEX = r"""
    (stone|cobblestone|\w+_ingot$|slime_ball|redstone|\w+smithing_template|bone_meal|
    wheat|quartz|resin_clump|coal|diamond|dried_kelp|emerald|honey_bottle|lapis_lazuli|white_wool|
    raw_\w+(?!_block)|\w+dye|leather)$
"""
MC_VERSION_REGEX = r"(\d+\.\d+(\.\d+(-\w+\d*)?)?|(\d{2}w\d{2}[a-z]))$"

# Crafting methods that are prioritised over others and can overwrite existing recipes
PRIORITY_CRAFTING_METHODS = {
    'crafting_shaped',
    'crafting_shapeless',
    'smithing_transform'
}

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
    "#netherite_tool_materials": "netherite_ingot",
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
    "scute": "turtle_scute", # XXX could also be armadillo scute??
    "grass": "short_grass",
    
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
INVALID_BLOCKS = {
    "air",
    "void_air",
    "cave_air",
    "fire",
    "soul_fire",
    "nether_portal",
    "end_portal",
    "piston_head", # yes you can have a piston head on its own, but it's rare and you can get the piston back anyways if you're skilled enough
}

BLOCKS_WITHOUT_ITEM = {
    "block36",
    "frosted_ice",
    "end_gateway",
    "light",
}

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
    "moving_piston": "block36",
}

# Entities that have the same name as their item form
SIMPLE_ENTITIES = {
    "painting",
    "armor_stand",
    "end_crystal",
}

# Entities that don't make sense to include in the items list
INVALID_ENTITIES = {
    "item"
}

# Keywords for matching headgear items on mobs
HEADGEAR_KWS = {
    "helmet",
    "head",
    "skull",
    "pumpkin",
}

# 'Craftable' golem-like entities
GOLEM_RECIPES = {
    "iron_golem": {"iron_block": 4, "carved_pumpkin": 1},
    "snow_golem": {"snow_block": 1, "carved_pumpkin": 1},
    "wither": {"soul_sand": 3, "wither_skeleton_skull": 3},
}

# Condenseable items that don't follow a specific naming pattern, e.g. ingots -> blocks
CONDENSABLES = {
    "bone_meal": ("bone_block", 9),
    "coal": ("coal_block", 9),
    "diamond": ("diamond_block", 9),
    "emerald": ("emerald_block", 9),
    "honey_bottle": ("honey_block", 4),
    "lapis_lazuli": ("lapis_block", 9),
    "redstone": ("redstone_block", 9),
    "slime_ball": ("slime_block", 9),
    "snowball": ("snow_block", 4),
    "wheat": ("hay_block", 9),
}

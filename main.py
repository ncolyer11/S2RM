from data.recipes_raw_mats_database_builder import generate_raw_materials_table_dict
from src.S2RM_frontend import start
from src.config import check_has_selected_mc_vers, update_config


# TODO
# - dont fully change config json seledted mc version till successfuly changred vers
# XXX issue when importing a lot of files sometimes the loading bar doesnt show after a bit
# but mainly the input materials list doesnt get reset and new stuff just gets appended to the end?
def main():
    # Check if the user's program or mc version needs updating/downloading
    update_config(redownload=False, delete=True)

    # Start the frontend
    start()

if __name__ == "__main__":
    check_has_selected_mc_vers(redownload=True)
    exit(0)
    main()

from data.download_game_data import check_mc_data
from s2rm.src.helpers import check_connection
from src.S2RM_frontend import start
from src.config import update_config

# XXX issue when importing a lot of files sometimes the loading bar doesnt show after a bit
# but mainly the input materials list doesnt get reset and new stuff just gets appended to the end?

def main():
    if check_connection():
        # Check if the user's program or mc version needs updating
        update_config()
        # Download the latest mc game data if the program's mc version is out of date
        check_mc_data(delete=True)

    # Start the frontend
    start()

if __name__ == "__main__":
    main()

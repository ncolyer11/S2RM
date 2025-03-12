from src.S2RM_frontend import start
from data.download_game_data import check_mc_data

# XXX issue when importing a lot of files sometimes the loading bar doesnt show after a bit
# but mainly the input materials list doesnt get reset and new stuff just gets appended to the end?


def main():
    # Download the latest mc game data if the program's mc version is out of date
    check_mc_data(delete=True)

    # Start the frontend
    start()

if __name__ == "__main__":
    main()

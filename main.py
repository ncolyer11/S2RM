from data.download_game_data import check_mc_version
from S2RM_frontend import start

def main():
    # Download the latest mc game data if the program's mc version is out of date
    check_mc_version()

    # Start the frontend
    start()

if __name__ == "__main__":
    main()

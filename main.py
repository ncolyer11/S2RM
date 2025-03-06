from src.S2RM_frontend import start
from data.download_game_data import check_mc_version

# Notes:
# XXX:
# - Both radio buttons get set to right state when reloading a json
# - Loading jsons doesn't do shiii

def main():
    # Download the latest mc game data if the program's mc version is out of date
    check_mc_version(delete=False)

    # Start the frontend
    start()

if __name__ == "__main__":
    main()

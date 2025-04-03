from src.S2RM_frontend import start
from src.config import update_config

# XXX issue when importing a lot of files sometimes the loading bar doesnt show after a bit
# but mainly the input materials list doesnt get reset and new stuff just gets appended to the end?

def main():
    # Check if the user's program or mc version needs updating/downloading
    update_config(redownload=False, delete=True)

    # Start the frontend
    start()

if __name__ == "__main__":
    main()

import sys
from interface import PokerInterface

def main():
    interface = PokerInterface()
    print("Interface created successfully")
    interface.run()

if __name__ == "__main__":
    main()
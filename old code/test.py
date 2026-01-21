from card import Card
from game import Game


def main():
    hand_validation_test()
    
def hand_validation_test():
    """
        A test that tests the robustness of the hand validation system such that,
        in case of something impossible happening, we can test it early before
        release.
    """
    g1 = Game(debug_mode=True)
    g1.set_cards([Card("Hearts", 14),Card("Hearts", 13),Card("Hearts", 12),Card("Hearts", 11),Card("Hearts", 10)], 
                 *[[Card("Spades",2),Card("Spades",3)],
                   [Card("Clubs",2),Card("Clubs",3)]])
    g1.start(1)
    g1.set_cards([Card("Clubs", 2),Card("Hearts", 2),Card("Hearts", 5),Card("Diamonds", 5),Card("Clubs", 13)], 
                 *[[Card("Spades",2),Card("Spades",5)],
                   [Card("Diamonds",2),Card("Clubs",7)]])
    g1.start(1)
    

if __name__ == "__main__":
    main()

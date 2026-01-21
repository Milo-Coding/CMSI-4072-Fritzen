from card import Card
import random

class Deck:
	def __init__(self):
		suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
		# Values: 2-10, Jack=11, Queen=12, King=13, Ace=14
		values = list(range(2, 15))
		self.cards = [Card(suit, value) for suit in suits for value in values]
		self._still_in_deck = self.cards.copy()

	def __len__(self):
		return len(self.cards)

	def shuffle(self):
		self._still_in_deck = self.cards.copy()
		random.shuffle(self._still_in_deck)

	def deal_card(self):
		if len(self._still_in_deck) == 0:
			raise ValueError("No cards left in the deck to deal.")
		return self._still_in_deck.pop()
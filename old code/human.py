from player import Player

class Human(Player):
    
    def __init__(self, hand=None, chips=0, name: str | None = None):
        super().__init__(hand, chips, name or "Human")

    def get_human_decision(self, available_actions, call_amount, current_table_bet, pot):
        """Get decision from human via command line input."""
        print(f"\n--- Your Turn ---")
        print(f"Your hand: {[f'{c.value} of {c.suit}' for c in self.hand]}")
        print(f"Your chips: {self.chips}")
        print(f"Pot: {pot}, Current bet: {current_table_bet}, To call: {call_amount}")
        print(f"Available actions: {', '.join(available_actions)}")
        
        while True:
            try:
                if "check" in available_actions and call_amount == 0:
                    action = input("Enter action (check/raise/allin/fold): ").strip().lower()
                elif "call" in available_actions:
                    action = input("Enter action (call/raise/allin/fold): ").strip().lower()
                else:
                    action = input("Enter action (call/raise/allin/fold): ").strip().lower()
                
                if action == "check" and "check" in available_actions:
                    return "check"
                elif action == "call" and "call" in available_actions:
                    return "call"
                elif action == "fold" and "fold" in available_actions:
                    return "fold"
                elif action == "raise" and ("raise" in available_actions or "bet" in available_actions):
                    
                    # Determine if this is a bet or raise
                    if current_table_bet == 0:
                        # It's a bet
                        min_bet = self.big_blind if hasattr(self, 'big_blind') else 10
                        max_bet = self.chips
                        bet_amount = int(input(f"Enter bet amount ({min_bet}-{max_bet}): "))
                        
                        if bet_amount < min_bet:
                            print(f"Bet must be at least {min_bet}")
                            continue
                        
                        if bet_amount > max_bet:
                            print(f"You only have {max_bet} chips")
                            continue
                        
                        return ("bet", bet_amount)
                    
                    else:
                        # It's a raise
                        min_raise = current_table_bet + (self.big_blind if hasattr(self, 'big_blind') else 10)
                        max_raise = self.chips + self.current_bet_in_round
                        raise_amount = int(input(f"Enter raise amount ({min_raise}-{max_raise}): "))
                        if raise_amount < min_raise:
                            print(f"Raise must be at least {min_raise}")
                            continue
                        if raise_amount > max_raise:
                            print(f"Maximum raise is {max_raise}")
                            continue
                        return ("raise", raise_amount)
                
                elif action == "allin":
                    return ("raise", self.chips + self.current_bet_in_round)
                
                else:
                    print("Invalid action or action not available. Try again.")
            
            except ValueError:
                print("Please enter a valid number.")
            
            except KeyboardInterrupt:
                print("\nGame interrupted by user.")
                return "fold"
import pygame
from game import Game
from player import Player
from agent import Agent
from card import Card

pygame.init()

from color import Color
from button import Button
from slider import Slider

"""
TODO LIST:

1. SLIDER FUNCTIONALITY:
   - Add mouse drag handling for raise amount slider
   - Implement click-and-drag functionality for slider knob
   - Add keyboard controls for fine-tuning raise amount (arrow keys)
   - Add step increments/decrements for slider
   - Validate raise amount stays within min/max bounds

2. ACTION BUTTONS:
   - Fix button positioning to not overlap with other UI elements
   - Add hover effects for buttons
   - Add disabled state for unavailable actions
   - Implement proper button spacing and alignment

3. GAME FLOW:
   - Fix betting round transitions
   - Implement proper hand completion logic
   - Fix pot distribution display

4. OVERLAPPING ELEMENTS:
   - Adjust player area positions to prevent overlap with community cards
   - Fix dealer button positioning relative to player areas
   - Ensure action buttons don't overlap with player info
   - Reposition community cards to avoid table edges

5. TEXT AND FONTS:
   - Implement text wrapping for long action results
   - Add proper font scaling for different screen sizes
   - Fix text alignment in player areas
   - Add chip count formatting (comma separators)

6. CARD DISPLAY:
   - Improve card visual design (suits, colors, borders)
   - Implement proper card reveal timing
   - Implement card images.

7. LAYOUT REFINEMENT:
   - Consistent spacing and margins throughout
   - Better visual hierarchy (important info more prominent)
   - Responsive element sizing
   - Improved color scheme and contrast

REFACTORING NEEDED:
-------------------
- Extract constants to config file
- Separate UI logic from game logic more cleanly
- Create reusable UI components (Button, Slider, CardDisplay)
- Implement proper MVC/MVP architecture
- Add comprehensive error handling
"""

# Base screen size (The original design size)
BASE_SCREEN_WIDTH = 1200
BASE_SCREEN_HEIGHT = 900

# Current screen size (for testing)
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 800

class LayoutManager:
    def __init__(self, screen_width, screen_height, base_width=BASE_SCREEN_WIDTH, base_height=BASE_SCREEN_HEIGHT):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.base_width = base_width
        self.base_height = base_height
        self.ratio_x = screen_width / base_width
        self.ratio_y = screen_height / base_height
        self.scale_factor = min(self.ratio_x, self.ratio_y)
        
    def scale_x(self, x):
        """Scale X coordinate from base to current screen"""
        return int(x * self.ratio_x)
    
    def scale_y(self, y):
        """Scale Y coordinate from base to current screen"""
        return int(y * self.ratio_y)
    
    def scale_size(self, size):
        """Scale size (width/height) maintaining aspect ratio"""
        return int(size * self.scale_factor)
    
    def scale_rect(self, x, y, width, height):
        """Scale a complete rectangle"""
        return (
            self.scale_x(x),
            self.scale_y(y),
            self.scale_size(width),
            self.scale_size(height)
        )
    
    # Pre-calculated positions (using base coordinates)
    @property
    def screen_center_x(self):
        return self.screen_width // 2
    
    @property
    def screen_center_y(self):
        return self.screen_height // 2
    
    @property
    def human_player_y(self):
        return self.scale_y(720)  # Base: 900 - 180
        
    @property
    def ai_player_y(self):
        return self.scale_y(180)  # Base: 180
    
    @property
    def action_buttons_x(self):
        return self.scale_x(200)  # Base: 200
        
    @property
    def action_buttons_y(self):
        return self.scale_y(820)  # Base: 900 - 80
        
    @property
    def community_cards_y(self):
        return self.scale_y(450)  # Base: 900/2 = 450
        
    @property
    def bet_slider_y(self):
        return self.scale_y(740)  # Base: 900 - 160
        
    @property
    def turn_indicator_y(self):
        return self.scale_y(625)  # Base: 900 - 100
        
    @property
    def pot_display_offset_x(self):
        return self.scale_x(0)  # Centered, so 0 offset   

    @property
    def pot_display_offset_y(self):
        return self.scale_y(130)  # Base: 130
        
    @property
    def current_bet_offset(self):
        return self.scale_y(160)  # Base: 160
        
    @property
    def community_label_offset(self):
        return self.scale_y(90)  # Base: 90
        
    @property
    def table_margin_x(self):
        return self.scale_x(150)  # Base: 150
        
    @property
    def table_margin_y(self):
        return self.scale_y(120)  # Base: 120
        
    @property
    def dealer_button_offset_x(self):
        return self.scale_x(250)  # Base: 250
        
    @property
    def dealer_button_offset_y(self):
        return self.scale_y(250)  # Base: 250
    
    @property
    def reset_game_button_offset_x(self):
        return self.scale_x(1000) # Base: 1000
    
    @property
    def reset_game_button_offset_y(self):
        return self.scale_y(800)  # Base: 800

# UI Constants
class UIConstants:
    def __init__(self, layout):
        self.layout = layout
        
    @property
    def card_width(self):
        return self.layout.scale_size(80)
    
    @property
    def card_height(self):
        return self.layout.scale_size(120)
    
    @property
    def card_spacing(self):
        return self.layout.scale_size(90)
    
    @property
    def button_width(self):
        return self.layout.scale_size(120)
    
    @property
    def button_height(self):
        return self.layout.scale_size(50)
    
    @property
    def player_area_width(self):
        return self.layout.scale_size(360)
    
    @property
    def player_area_height(self):
        return self.layout.scale_size(160)
    
    @property
    def bet_slider_width(self):
        return self.layout.scale_size(400)
    
    @property
    def bet_slider_height(self):
        return self.layout.scale_size(80)
    
    @property
    def training_button_width(self):
        return self.layout.scale_size(150)
    
    @property
    def training_button_height(self):
        return self.layout.scale_size(40)

# Colors
DARK_GREEN = (0, 100, 0)
LIGHT_GREEN = (0, 150, 0)
RED = (255, 0, 0)
BLUE = (0, 100, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
GRAY = (150, 150, 150)
YELLOW = (255, 255, 0)
DARK_BLUE = (0, 0, 139)

class PokerInterface:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED)
        pygame.display.set_caption("Texas Hold'em Poker")

        # Initialize layout manager and UI constants
        self.layout = LayoutManager(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.ui = UIConstants(self.layout)
        
        self.clock = pygame.time.Clock()
        
        # Fonts with scaling
        base_font_size = 32
        scaled_font_size = self.layout.scale_size(base_font_size)
        self.title_font = pygame.font.Font(None, scaled_font_size)
        self.font = pygame.font.Font(None, scaled_font_size)
        self.small_font = pygame.font.Font(None, self.layout.scale_size(24))
        
        self.slider_dragging = False
        self.slider_rect = None
        
        # Start Loading Screen
        self.draw_loading()

        # Game state
        self.game = Game(small_blind=10, start_total=1000, num_players=2, human_player_index=0)
        self.current_hand = 1
        self.game_active = True
        self.waiting_for_action = False
        self.selected_action = None
        self.bet_amount = 0
        self.min_bet = 0
        self.max_bet = 0
        self.action_result = ""
        self.training_mode = False
        self.training_stats = {"hands_played": 0, "ai_wins": 0, "ai_losses": 0}
        self.show_slider = False

        # Intializes Classes
        Button.interface = self.screen 
        Slider.interface = self.screen 
        Slider.debug_mode = False       
        Card.initialize_card_back()
        
        # Game Objects
        action_button_spacing = self.layout.scale_size(3)
        start_y = self.layout.screen_height * 11 // 16
        self.check_button: Button = Button(
            x=self.layout.action_buttons_x,
            y=start_y,
            width=self.ui.button_width,
            height=self.ui.button_height,
            text="Check",
            font=self.font,
            enabled=False,
            action=self._on_check_button_clicked
        )
        self.call_button: Button = Button(
            x=self.layout.action_buttons_x,
            y=start_y + self.ui.button_height + action_button_spacing,
            width=self.ui.button_width,
            height=self.ui.button_height,
            text="Call",
            font=self.font,
            enabled=False,
            action=self._on_call_button_clicked
        )
        self.raise_button: Button = Button(
            x=self.layout.action_buttons_x,
            y=start_y + 2 * (self.ui.button_height + action_button_spacing),
            width=self.ui.button_width,
            height=self.ui.button_height,
            toggle_color=Color.YELLOW,
            text="Raise",
            font=self.font,
            toggle=False,
            toggleable=True,
            enabled=False,
            action=self._on_raise_button_clicked
        )
        self.all_in_button: Button = Button(
            x=self.layout.action_buttons_x,
            y=start_y + 3 *(self.ui.button_height + action_button_spacing),
            width=self.ui.button_width,
            height=self.ui.button_height,
            text="All In",
            font=self.font,
            enabled=False,
            action=self._on_all_in_button_clicked
        )
        self.fold_button: Button = Button(
            x=self.layout.action_buttons_x,
            y=start_y + 4 *(self.ui.button_height + action_button_spacing),
            width=self.ui.button_width,
            height=self.ui.button_height,
            text="Fold",
            font=self.font,
            enabled=False,
            action=self._on_fold_button_clicked
        )
        self.raise_submit_button: Button = Button(
            x=self.layout.screen_center_x - (self.ui.button_width) // 2,
            y=self.layout.bet_slider_y + 75,
            width=self.ui.button_width,
            height=self.ui.button_height,
            color=Color.NEON_GREEN,
            hover_color=Color.LIGHT_NEON_GREEN,
            pressed_color=Color.LIGHT_GREEN,
            text="Submit",
            font=self.font,
            visible=False,
            action=self._on_raise_submit_button_clicked
        )
        margin = self.layout.scale_size(20)
        training_button_x = self.layout.screen_width - self.ui.training_button_width - margin
        self.training_mode_button: Button = Button(
            x=training_button_x,
            y=self.layout.scale_size(10),
            width=self.ui.training_button_width,
            height=self.ui.training_button_height,
            toggle_color=Color.YELLOW,
            text="Training: OFF",
            text_toggled="Training: ON",
            font=self.font,
            toggle=False,
            toggleable=True,
            action=self._on_train_mode_button_clicked
        )
        self.reset_ai_button: Button = Button(
            x=training_button_x - self.ui.training_button_width - self.layout.scale_size(10),
            y=self.layout.scale_size(10),
            width=self.ui.training_button_width,
            height=self.ui.training_button_height,
            color=Color.RED,
            hover_color=Color.LIGHT_RED,
            pressed_color=Color.DARK_RED,
            text="Reset AI",
            font=self.font,
            font_color=Color.WHITE,
            action=self.game.reset_ai_models
        )
        margin = self.layout.scale_size(10)
        self.new_round_button: Button = Button(
            x=self.layout.reset_game_button_offset_x - self.ui.button_width // 2,
            y=self.layout.reset_game_button_offset_y - self.ui.button_height // 2 - self.ui.button_height - margin,
            width=self.ui.button_width,
            height=self.ui.button_height,
            text="New Round",
            font=self.font,
            visible=False,
            action=self._on_new_round_button_clicked
        )
        self.new_game_button: Button = Button(
            x=self.layout.reset_game_button_offset_x - self.ui.button_width // 2,
            y=self.layout.reset_game_button_offset_y - self.ui.button_height // 2,
            width=self.ui.button_width,
            height=self.ui.button_height,
            color=Color.RED,
            hover_color=Color.LIGHT_RED,
            pressed_color=Color.DARK_RED,
            text="New Game",
            font=self.font,
            font_color=Color.WHITE,
            visible=False,
            action=self._on_new_game_button_clicked
        )
        self.buttons = [
            self.check_button,
            self.call_button,
            self.raise_button,
            self.all_in_button,
            self.fold_button,
            self.raise_submit_button,
            self.training_mode_button,
            self.reset_ai_button,
            self.new_round_button,
            self.new_game_button,
        ]
        self.buttons_val = [None] * len(self.buttons)

        # UI
        CURSOR_STRING = (
            ".                       ",
            "..                      ",
            ".X.                     ",
            ".XX.                    ",
            ".XXX.                   ",
            ".XXXX.                  ",
            ".XXXXX.                 ",
            ".XXXXXX.                ",
            ".XXXXXXX.               ",
            ".XXXXXXXX.              ",
            ".XXXXXXXXX.             ",
            ".XXXXXXXXXX.            ",
            ".XXXXXX.....            ",
            ".XXX.XX.                ",
            ".XX. .XX.               ",
            ".X.  .XX.               ",
            "..    .XX.              ",
            "      .XX.              ",
            "       ..               ",
            "                        ",
            "                        ",
            "                        ",
            "                        ",
            "                        "
        )
        SELECT_CURSOR_STRING = (
            "     ..                 ",
            "    .XX.                ",
            "    .XX.                ",
            "    .XX.                ",
            "    .XX.                ",
            "    .XX.                ",
            "    .XX...              ",
            "    .XX.XX...           ",
            "    .XX.XX.XX..         ",
            "    .XX.XX.XX.X.        ",
            "... .XX.XX.XX.XX.       ",
            ".XX..XXXXXXXX.XX.       ",
            ".XXX.XXXXXXXXXXX.       ",
            " .XX.XXXXXXXXXXX.       ",
            "  .X.XXXXXXXXXXX.       ",
            "  .XXXXXXXXXXXXX.       ",
            "   .XXXXXXXXXXXX.       ",
            "   .XXXXXXXXXXX.        ",
            "    .XXXXXXXXXX.        ",
            "    .XXXXXXXXXX.        ",
            "     .XXXXXXXX.         ",
            "     .XXXXXXXX.         ",
            "     ..........         ",
            "                        "
        )
        self.cursor = pygame.cursors.compile(CURSOR_STRING)
        self.select_cursor = pygame.cursors.compile(SELECT_CURSOR_STRING)
        self.pointing = False

        # Store human decision for when game asks for it
        self.human_decision = None
        self.human_decision_ready = False
        
        # Start the first hand
        self.start_new_hand()

    def start_new_hand(self):
        """Start a new poker hand"""
        self.game._prepare_new_hand()
        self.game._post_blinds()
        self.game._deal_hole_cards()
        self.selected_action = None
        self.action_result = ""
        self.human_decision = None
        self.human_decision_ready = False
        self.update_game_info("New hand started - Pre-Flop betting")
        
        # Let game.py handle the entire pre-flop betting round
        self.run_betting_round("Pre-Flop")

    def update_game_info(self, info):
        """Update the action result display"""
        self.action_result = info
        print(info)

    def draw_table(self):
        """Draw the poker table with proper spacing"""
        self.screen.fill(DARK_GREEN)
        
        # Draw table oval using scaled dimensions - access through layout
        table_width = self.layout.screen_width - 2 * self.layout.table_margin_x
        table_height = self.layout.screen_height - 2 * self.layout.table_margin_y
        table_rect = (self.layout.table_margin_x, self.layout.table_margin_y, table_width, table_height)
        pygame.draw.ellipse(self.screen, LIGHT_GREEN, table_rect)
        pygame.draw.ellipse(self.screen, BLACK, table_rect, 5)
        
        # Draw dealer button
        self.draw_dealer_button()

    def draw_dealer_button(self):
        """Draw the dealer button with proper positioning"""
        if self.game.dealer_index == 0:  # Human is dealer
            dealer_x = self.layout.screen_center_x - self.layout.dealer_button_offset_x
            dealer_y = self.layout.screen_height - self.layout.dealer_button_offset_y
        else:  # AI is dealer
            dealer_x = self.layout.screen_center_x - self.layout.dealer_button_offset_x
            dealer_y = self.layout.dealer_button_offset_y
        
        # Draw dealer button with scaled radius
        button_radius = self.layout.scale_size(20)
        pygame.draw.circle(self.screen, WHITE, (dealer_x, dealer_y), button_radius)
        pygame.draw.circle(self.screen, BLACK, (dealer_x, dealer_y), button_radius, 2)
        dealer_text = self.small_font.render("D", True, BLACK)
        text_rect = dealer_text.get_rect(center=(dealer_x, dealer_y))
        self.screen.blit(dealer_text, text_rect)

    def draw_players(self):
        """Draw all players"""
        # Human player (bottom)
        human_player = self.game.players[0]
        self.draw_player(self.layout.screen_center_x, self.layout.human_player_y, human_player, is_human=True)
        
        # AI player (top)
        ai_player = self.game.players[1]
        self.draw_player(self.layout.screen_center_x, self.layout.ai_player_y, ai_player, is_human=False)

    def draw_player(self, center_x: int, center_y: int, player: Player, is_human: bool):
        """Draw a player's area"""
        # Highlight active player
        if self.waiting_for_action and is_human:
            border_color = YELLOW
            border_width = 4
        else:
            border_color = DARK_BLUE if is_human else RED
            border_width = 2
        
        # Draw player area
        player_rect_x = center_x - self.ui.player_area_width // 2
        player_rect_y = center_y - self.ui.player_area_height // 2
        player_rect = (player_rect_x, player_rect_y, self.ui.player_area_width, self.ui.player_area_height)
        pygame.draw.rect(self.screen, border_color, player_rect, border_width, border_radius=10)
        
        # Player info section
        info_offset_x = self.layout.scale_size(160)
        info_x = center_x - info_offset_x
        name_text = self.font.render(f"{player.name}", True, WHITE)
        chips_text = self.font.render(f"${player.chips}", True, GOLD)
        self.screen.blit(name_text, (info_x, center_y - 70))
        self.screen.blit(chips_text, (info_x, center_y - 40))
        
        # Current bet in round
        if player.current_bet_in_round > 0:
            bet_text = self.small_font.render(f"Bet: ${player.current_bet_in_round}", True, WHITE)
            self.screen.blit(bet_text, (info_x, center_y - 10))
        
        # Draw cards with better spacing
        if hasattr(player, 'hand') and player.hand:
            card_offset_x = self.layout.scale_size(80)
            card_start_x = center_x - card_offset_x
            card_y_offset = self.layout.scale_size(30)
            card_y = center_y + card_y_offset
            
            for card_index, card in enumerate(player.hand):
                card_x = card_start_x + card_index * self.ui.card_spacing
                if is_human or not player.is_playing_round or not self.game_active:
                    self.draw_card(card_x, card_y, card)
                else:
                    self.draw_card_back(card_x, card_y)
        
        # Fold indicator
        if not player.is_playing_round:
            fold_text = self.font.render("FOLDED", True, RED)
            fold_rect = fold_text.get_rect(center=(center_x, center_y - 50))
            self.screen.blit(fold_text, fold_rect)

    def draw_card(self, card_x: int, card_y: int, card):
        """Draw a card with better styling"""
        # Card background with rounded corners
        card_rect = pygame.Rect(card_x, card_y, self.ui.card_width, self.ui.card_height)

        img_width = card.card_img.get_rect().width
        img_height = card.card_img.get_rect().height
        scale_factor = 30
        card_img = pygame.transform.scale(card.card_img, (img_width/scale_factor, img_height/scale_factor))
        self.screen.blit(card_img, card_rect)

    def draw_card_back(self, card_x: int, card_y: int):
        """Draw a card back with better styling"""
        card_rect = pygame.Rect(card_x, card_y, self.ui.card_width, self.ui.card_height)

        img_width = Card.card_back_img.get_rect().width
        img_height = Card.card_back_img.get_rect().height
        scale_factor = 30
        card_img = pygame.transform.scale(Card.card_back_img, (img_width/scale_factor, img_height/scale_factor))
        self.screen.blit(card_img, card_rect)

    def draw_community_cards(self):
        """Draw community cards with better spacing"""
        if hasattr(self.game, 'community_cards'):
            community_cards = self.game.community_cards
            if community_cards:
                # Calculate total width needed and start position
                total_cards_width = len(community_cards) * self.ui.card_spacing - 10
                start_x = self.layout.screen_center_x - total_cards_width // 2
                
                for card_index, card in enumerate(community_cards):
                    card_x = start_x + card_index * self.ui.card_spacing
                    self.draw_card(card_x, self.layout.community_cards_y, card)
                
                # Label for community cards
                community_text = self.font.render("Community Cards", True, WHITE)
                text_rect = community_text.get_rect(center=(self.layout.screen_center_x, self.layout.screen_center_y - self.layout.community_label_offset))
                self.screen.blit(community_text, text_rect)

    def draw_pot(self):
        """Draw pot amount with better positioning"""
        pot_text = self.font.render(f"Pot: ${self.game.pot}", True, GOLD)
        pot_rect = pot_text.get_rect(center=(self.layout.screen_center_x, self.layout.screen_center_y - self.layout.pot_display_offset_y))
        self.screen.blit(pot_text, pot_rect)
        
        # Current bet to call
        if hasattr(self.game, 'current_table_bet'):
            bet_text = self.small_font.render(f"Current Bet: ${self.game.current_table_bet}", True, WHITE)
            bet_rect = bet_text.get_rect(center=(self.layout.screen_center_x, self.layout.screen_center_y - self.layout.current_bet_offset))
            self.screen.blit(bet_text, bet_rect)

    def enable_action_buttons(self):
        """Enable action buttons if they follow certain conditions"""
        human_player = self.game.players[0]
        call_amount = self.game.current_table_bet - human_player.current_bet_in_round
        available_actions = self.game._get_available_actions(human_player, call_amount)
        enabled = self.waiting_for_action and human_player.is_playing_round

        self.check_button.enabled  = enabled and "check" in available_actions
        self.call_button.enabled   = enabled and "call" in available_actions
        self.raise_button.enabled  = enabled and "raise" in available_actions
        # All-in is handled through raise with max bet amount, so disable dedicated button
        self.all_in_button.enabled = False
        self.fold_button.enabled   = enabled and "fold" in available_actions
            
    def draw_betting_slider(self):
        """Draw a universal betting slider for both bet and raise actions"""
        self.raise_submit_button.visible = False
        if not self.show_slider:
            return 
        if not self.waiting_for_action:
            return
            
        human_player = self.game.players[0]
        if not human_player.is_playing_round:
            return
            
        call_amount = self.game.current_table_bet - human_player.current_bet_in_round
        available_actions = self.game._get_available_actions(human_player, call_amount)
        
        # Calculate min and max bet amounts
        # Only show slider if betting or raising is available
        if "bet" in available_actions:
            self.min_bet = self.game.big_blind
            self.max_bet = human_player.chips
            action_type = "Bet"
        elif "raise" in available_actions:
            self.min_bet = self.game.current_table_bet + self.game.big_blind
            self.max_bet = human_player.chips + human_player.current_bet_in_round
            action_type = "Raise"
        else: 
            return
        
        # Ensure bet amount is within bounds
        self.bet_amount = max(self.min_bet, min(self.bet_amount, self.max_bet))
        
        # Position slider
        slider_x = (self.layout.screen_width - self.ui.bet_slider_width) // 2
        
        # Background with rounded corners
        slider_bg_rect = pygame.Rect(slider_x, self.layout.bet_slider_y, self.ui.bet_slider_width, self.ui.bet_slider_height)
        pygame.draw.rect(self.screen, (60, 60, 60), slider_bg_rect, border_radius=8)
        pygame.draw.rect(self.screen, BLACK, slider_bg_rect, 2, border_radius=8)
        
        # Title based on action type
        title_text = self.small_font.render(f"{action_type} Amount: ${self.bet_amount:,}", True, WHITE)
        title_rect = title_text.get_rect(center=(slider_x + self.ui.bet_slider_width // 2, self.layout.bet_slider_y + 20))
        self.screen.blit(title_text, title_rect)
        
        # Min/Max labels
        min_text = self.small_font.render(f"Min: ${self.min_bet:,}", True, WHITE)
        max_text = self.small_font.render(f"Max: ${self.max_bet:,}", True, WHITE)
        self.screen.blit(min_text, (slider_x + 20, self.layout.bet_slider_y + 40))
        self.screen.blit(max_text, (slider_x + self.ui.bet_slider_width - max_text.get_width() - 20, self.layout.bet_slider_y + 40))
        
        # Slider track
        track_start_x = slider_x + 80
        track_width = self.ui.bet_slider_width - 160
        track_y = self.layout.bet_slider_y + 55
        
        # Store slider rect for mouse interaction
        track_height = self.layout.scale_size(8)
        self.slider_rect = pygame.Rect(track_start_x, track_y - track_height//2, 
                                    track_width, track_height)
        
        # Draw slider track
        pygame.draw.rect(self.screen, DARK_BLUE, self.slider_rect, border_radius=track_height//2)
        pygame.draw.rect(self.screen, WHITE, self.slider_rect, 1, border_radius=track_height//2)
        
        # Draw slider knob
        if self.max_bet > self.min_bet:
            slider_position = track_start_x + (self.bet_amount - self.min_bet) / (self.max_bet - self.min_bet) * track_width
            knob_radius = self.layout.scale_size(12)
            knob_color = YELLOW if self.slider_dragging else RED
            pygame.draw.circle(self.screen, knob_color, (int(slider_position), track_y), knob_radius)
            pygame.draw.circle(self.screen, BLACK, (int(slider_position), track_y), knob_radius, 2)
            
            # Draw tick marks at key positions
            tick_positions = [0.0, 0.25, 0.5, 0.75, 1.0]
            for pos in tick_positions:
                tick_x = track_start_x + pos * track_width
                pygame.draw.line(self.screen, WHITE, (tick_x, track_y - 8), (tick_x, track_y + 8), 2)

        # Draw slider submit
        self.raise_submit_button.visible = True

    def draw_game_info(self):
        """Draw game state information with better layout"""
        # Top info bar
        info_bar_height = self.layout.scale_size(40)
        info_bar_rect = pygame.Rect(0, 0, self.layout.screen_width, info_bar_height)
        pygame.draw.rect(self.screen, DARK_BLUE, info_bar_rect)
        pygame.draw.line(self.screen, WHITE, (0, info_bar_height), (self.layout.screen_width, info_bar_height), 2)
        
        # Training statistics
        if self.training_mode:
            ai_player = self.game.players[1]
            if isinstance(ai_player, Agent):
                stats_text = f"Episodes: {ai_player.training_episodes} | " \
                           f"Wins: {ai_player.wins} | Losses: {ai_player.losses} | " \
                           f"ε: {ai_player.epsilon:.3f}"
                stats_surface = self.small_font.render(stats_text, True, WHITE)
                self.screen.blit(stats_surface, (self.layout.scale_size(20), self.layout.scale_size(60)))
        
        # Action result display (left)
        margin = self.layout.scale_size(20)
        if self.action_result:
            info_text = self.font.render(self.action_result, True, WHITE)
            self.screen.blit(info_text, (margin, 10))
        
        # Hand number (right)
        hand_text = self.small_font.render(f"Hand: {self.current_hand}", True, WHITE)
        hand_rect = hand_text.get_rect(right=self.layout.screen_width - margin, centery=info_bar_height//2)
        self.screen.blit(hand_text, hand_rect)
        
        # Current player turn
        if self.waiting_for_action:
            turn_text = self.font.render("Your Turn!", True, YELLOW)
        else:
            turn_text = self.font.render("AI Thinking...", True, WHITE)
        turn_rect = turn_text.get_rect(center=(self.layout.screen_center_x, self.layout.turn_indicator_y))
        self.screen.blit(turn_text, turn_rect)
        
        # Draw new game button if game is not active
        self.new_round_button.visible = not self.game_active and self.game.is_still_playable()
        self.new_game_button.visible = not self.game_active

    # Event handling and game logic methods
    def handle_events(self):
        """Handle PyGame events"""
        mouse_buttons = pygame.mouse.get_pressed()
        mouse_pos = pygame.mouse.get_pos()

        Button.update_click(False)
        Button.update_left_mouse_hold(mouse_buttons[0])
        Button.update_mouse_position(mouse_pos)
        Slider.update_left_mouse_hold(mouse_buttons[0])
        Slider.update_mouse_position(mouse_pos)
        
        # Handle slider dragging
        self.handle_slider_interaction(mouse_pos, mouse_buttons)
        
        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:               # Quit
                    quit()
                    return False
                # Mouse Controls
                case pygame.MOUSEBUTTONUP:      # Mouse Controls
                    Button.update_click(True)
                case pygame.KEYDOWN:            # Keyboard Controls
                    match event.key:
                        case pygame.K_SPACE if not self.game_active:
                            self.start_new_hand()
                            self.game_active = True
                        case pygame.K_RETURN if self.selected_action:
                            self.execute_action()
                        case pygame.K_t:        # T key to toggle training
                            self.training_mode_button.toggle = not self.training_mode_button.toggle
                            self.training_mode = not self.training_mode
                            self.game.set_training_mode(self.training_mode)
                        case pygame.K_r:        # R key to reset AI
                            self.game.reset_ai_models()
                        case _:
                            # Handle bet amount keyboard controls
                            self.handle_bet_keyboard(event)
        return True

    def handle_bet_keyboard(self, event):
        """Handle keyboard controls for bet amount"""
        if not self.waiting_for_action:
            return
            
        human_player = self.game.players[0]
        call_amount = self.game.current_table_bet - human_player.current_bet_in_round
        available_actions = self.game._get_available_actions(human_player, call_amount)
        
        # Only handle keyboard if betting or raising is available
        can_bet_or_raise = "bet" in available_actions or "raise" in available_actions
        if not can_bet_or_raise:
            return
        
        bb = self.game.big_blind
        
        match event.key:
            case pygame.K_LEFT:
                self.bet_amount = max(self.min_bet, self.bet_amount - bb)
            case pygame.K_RIGHT:
                self.bet_amount = min(self.max_bet, self.bet_amount + bb)
            case pygame.K_UP:
                self.bet_amount = min(self.max_bet, self.bet_amount + 5 * bb)
            case pygame.K_DOWN:
                self.bet_amount = max(self.min_bet, self.bet_amount - 5 * bb)
            case pygame.K_PAGEUP:
                half_pot = self.game.pot // 2
                self.bet_amount = min(self.max_bet, max(self.min_bet, self.round_to_bb(half_pot)))
            case pygame.K_PAGEDOWN:
                pot_size = self.game.pot
                self.bet_amount = min(self.max_bet, max(self.min_bet, self.round_to_bb(pot_size)))
            case pygame.K_HOME:
                self.bet_amount = self.min_bet
            case pygame.K_END:
                self.bet_amount = self.max_bet

    def handle_slider_interaction(self, mouse_position, mouse_buttons):
        """Handle slider drag and click interactions"""
        if not self.slider_rect or not self.waiting_for_action:
            return False
            
        human_player = self.game.players[0]
        call_amount = self.game.current_table_bet - human_player.current_bet_in_round
        available_actions = self.game._get_available_actions(human_player, call_amount)
        
        # Only handle slider if betting or raising is available
        can_bet_or_raise = "bet" in available_actions or "raise" in available_actions
        if not can_bet_or_raise:
            return False
        
        if mouse_buttons[0]:  # Left mouse button
            if self.slider_dragging or self.slider_rect.collidepoint(mouse_position):
                self.slider_dragging = True
                
                # Calculate new bet amount based on mouse position
                relative_x = max(0, min(mouse_position[0] - self.slider_rect.left, self.slider_rect.width))
                percentage = relative_x / self.slider_rect.width
                
                # Calculate raw amount
                raw_amount = self.min_bet + percentage * (self.max_bet - self.min_bet)
                
                # Snap to big blind increments for more intuitive betting
                if "bet" in available_actions:
                    self.bet_amount = max(self.min_bet, min(self.round_to_bb(raw_amount), self.max_bet))
                else:
                    self.bet_amount = max(self.min_bet, min(self.round_to_bb(raw_amount), self.max_bet))
                
                return True
        else:
            self.slider_dragging = False
            
        return False

    def round_to_bb(self, amount):
        """Round amount to nearest big blind increment"""
        bb = self.game.big_blind
        return max(bb, round(amount / bb) * bb)

    def execute_action(self):
        """Execute the selected action - store it for game.py to retrieve"""
        self.show_slider = False
        self.raise_button.toggle = False
        match self.selected_action:
            case "check":
                self.human_decision = "check"
            case "call":
                self.human_decision = "call"
            case "fold":
                self.human_decision = "fold"
            case "bet":
                self.human_decision = ("bet", self.bet_amount)
            case "raise":
                self.human_decision = ("raise", self.bet_amount)
            case _:
                return

        # Signal that decision is ready
        self.human_decision_ready = True
        self.waiting_for_action = False
        self.selected_action = None
        self.bet_amount = 0

    def run_betting_round(self, state_name: str):
        """Run a complete betting round using game.py logic"""
        # Temporarily override the human player's decision method
        human_player = self.game.players[0]
        original_method = human_player.get_human_decision
        
        def ui_get_decision(available_actions, call_amount, current_table_bet, pot):
            """Pause execution and wait for UI input"""
            self.waiting_for_action = True
            self.human_decision_ready = False
            self.human_decision = None
            
            # Wait for player to make a decision via UI
            while not self.human_decision_ready:
                # Process UI events while waiting
                if not self.handle_events():
                    return "fold"  # Player quit
                self.draw()
            
            return self.human_decision
        
        # Override method temporarily
        human_player.get_human_decision = ui_get_decision
        
        try:
            # Let game.py handle the entire betting round
            self.game._betting_round(state_name)
        finally:
            # Restore original method
            human_player.get_human_decision = original_method
        
        # After betting round completes
        if self.game._hand_over():
            self.game._award_pot_if_single()
            self.game_active = False
            self.current_hand += 1
        else:
            # Continue to next street
            self.advance_to_next_street()

    def advance_to_next_street(self):
        """Move to the next community card dealing phase"""
        community_count = len(self.game.community_cards)
        
        if community_count == 0:
            self.game._deal_community(3)
            self.update_game_info("Flop dealt")
            self.run_betting_round("Flop")
        elif community_count == 3:
            self.game._deal_community(1)
            self.update_game_info("Turn dealt")
            self.run_betting_round("Turn")
        elif community_count == 4:
            self.game._deal_community(1)
            self.update_game_info("River dealt")
            self.run_betting_round("River")
        else:
            # All streets complete, showdown
            self.game._showdown()
            self.game_active = False
            self.current_hand += 1

    def handle_showdown(self):
        self.game._showdown()
        self.update_game_info("Showdown complete")
        self.game_active = False
        self.current_hand += 1

    def handle_hand_end(self):
        self.game._award_pot_if_single()
        self.update_game_info("Hand ended - award pot")
        self.game_active = False
        self.current_hand += 1

    ###############################

    def draw_loading(self):
        loading_text = self.font.render("Loading...", True, WHITE)
        loading_rect = loading_text.get_rect(center=(self.layout.screen_center_x, self.layout.screen_center_y))
        self.screen.blit(loading_text, loading_rect)
        pygame.display.flip()
        
    def update_buttons(self):
        for i, b in enumerate(self.buttons):
            if b.is_hovered():
                self.pointing = True
            b.draw()
            self.buttons_val[i] = b.trigger()

    def update_cursor(self):
        if self.pointing:
            pygame.mouse.set_cursor((24, 24), (6, 1), *self.select_cursor)
        else:
            pygame.mouse.set_cursor((24, 24), (0, 0), *self.cursor)
        self.pointing = False

    def _on_check_button_clicked(self):
        self.selected_action = "check"
        self.execute_action()
    
    def _on_call_button_clicked(self):
        self.selected_action = "call"
        self.execute_action()
    
    def _on_raise_button_clicked(self):
        self.show_slider = self.raise_button.toggle
    
    def _on_raise_submit_button_clicked(self):
        self.selected_action = "raise"
        self.execute_action()
    
    def _on_all_in_button_clicked(self):
        self.selected_action = "all in"
        self.execute_action()

    def _on_fold_button_clicked(self):
        self.selected_action = "fold"
        self.execute_action()

    def _on_train_mode_button_clicked(self):
        self.training_mode = self.training_mode_button.toggle
        self.game.set_training_mode(self.training_mode)

    def _on_new_round_button_clicked(self):
        self.game_active = True
        self.start_new_hand()

    def _on_new_game_button_clicked(self):
        self.game = Game(small_blind=10, start_total=1000, num_players=2, human_player_index=0)
        self.game_active = True
        self.start_new_hand()

    def draw(self):
        """Draw the entire game state"""
        self.draw_table()
        self.draw_players()
        self.draw_community_cards()
        self.draw_pot()
        self.draw_betting_slider()
        self.draw_game_info()
        
        self.enable_action_buttons()
        self.update_buttons()
        self.update_cursor()
        
        pygame.display.flip()
        self.clock.tick(60)

    def run(self):
        """Main game loop"""
        running = True
        while running:
            running = self.handle_events()
            self.draw()
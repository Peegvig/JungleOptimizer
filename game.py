import time
import pygame
import sys
import random
from walls import *
from characters import *
from util import *

class JungleOptimizer():
    
    def __init__(self, window_width, window_height, world_height, world_width, fps, champion="Amumu", sound=False):
        
        self.window_width = window_width
        self.window_height = window_height
        self.world_height = world_height
        self.world_width = world_width
        
        self.paused = False

        pygame.init()
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("Jungle Optimizer")
        self.font = pygame.font.SysFont(None, 36)
        self.clock = pygame.time.Clock()
        self.fps = fps

        self.walls = walls_1

        # Create player champion based on selection
        self.champion_name = champion
        if champion.lower() == "amumu":
            self.player = Amumu(world_width, world_height, walls_1)
        elif champion.lower() == "lee_sin":
            self.player = LeeSin(world_width, world_height, walls_1)
        elif champion.lower() == "elise":
            self.player = Elise(world_width, world_height, walls_1)
        else:
            # Default to Amumu if champion not found
            print(f"Champion '{champion}' not found. Defaulting to Amumu.")
            self.player = Amumu(world_width, world_height, walls_1)

        # Create enemy Blue
        self.blue = Blue(world_width, world_height)

        # Camera position (centered on player at start)
        self.camera_x = self.player.x - self.window_width // 2
        self.camera_y = self.player.y - self.window_height // 2
        
        # Camera follow settings
        self.camera_following = False  # Only follow when SPACE is held

        # Right-click dragging
        self.right_mouse_pressed = False

        self.background_color = (181, 101, 29)
        self.wall_color = (1, 50, 32)
        self.border_color = (255, 0, 0)
        
        # Load backdrop image (optional - falls back to color if not found)
        try:
            self.backdrop = pygame.image.load("images/SRminimap4x.png")
            # Scale backdrop to be much bigger (3x the world size)
            backdrop_scale = 5
            self.backdrop = pygame.transform.scale(self.backdrop, (world_width * backdrop_scale, world_height * backdrop_scale))
        except:
            self.backdrop = None
        self.announcement_font = pygame.font.SysFont(None, 100)
        
        self.score = 0


    def fill_background(self):

        # Draw backdrop image or fallback to color
        if self.backdrop:
            self.screen.blit(self.backdrop, (-self.camera_x, -self.camera_y))
        else:
            self.screen.fill(self.background_color)

        # Update camera to follow player only if holding SPACE
        if self.camera_following:
            self.camera_x = self.player.x - self.window_width // 2
            self.camera_y = self.player.y - self.window_height // 2

        
        # Draw player and enemies
        self.player.draw(self.screen, self.camera_x, self.camera_y)
        self.blue.draw(self.screen, self.camera_x, self.camera_y)

        # Display champion info
        champ_surface = self.font.render(f"Champion: {self.champion_name}", True, (255, 0, 0))
        self.screen.blit(champ_surface, (10, 10))
        
        # Display health and mana
        hp_surface = self.font.render(f"HP: {self.player.hp}/{self.player.max_hp}", True, (0, 255, 0))
        self.screen.blit(hp_surface, (10, 50))
        
        mana_surface = self.font.render(f"Mana: {self.player.mana}/{self.player.max_mana}", True, (0, 0, 255))
        self.screen.blit(mana_surface, (10, 90))
        
        score_surface = self.font.render(f"Score: {self.score}", True, (255, 0, 0))
        self.screen.blit(score_surface, (10, 130))

    def step(self):

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click - helper to get coordinates
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x + self.camera_x
                    world_y = mouse_y + self.camera_y
                    print(f"Left-clicked at: x={world_x:.1f}, y={world_y:.1f}")
                elif event.button == 3:  # Right click pressed
                    self.right_mouse_pressed = True
                    # Convert screen position to world position
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x + self.camera_x
                    world_y = mouse_y + self.camera_y
                    self.player.set_target(world_x, world_y)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:  # Right click released
                    self.right_mouse_pressed = False
            elif event.type == pygame.MOUSEMOTION:
                # Update target while right-clicking and dragging
                if self.right_mouse_pressed:
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x + self.camera_x
                    world_y = mouse_y + self.camera_y
                    self.player.set_target(world_x, world_y)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif event.key == pygame.K_SPACE:
                    # Snap camera to player when SPACE is pressed
                    self.camera_x = self.player.x - self.window_width // 2
                    self.camera_y = self.player.y - self.window_height // 2
                    self.camera_following = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    self.camera_following = False
                elif event.key == pygame.K_a:
                    self.player.cast_auto_attack()
                elif event.key == pygame.K_q:
                    self.player.cast_q()
                elif event.key == pygame.K_w:
                    self.player.cast_w()
                elif event.key == pygame.K_e:
                    self.player.cast_e()

        # Update champion movement and cooldowns
        self.player.update_movement(collide_with=self.blue)
        self.player.update_cooldowns()

        self.fill_background()

        pygame.display.flip() # Updates display
        self.clock.tick(self.fps)  # Cap framerate at specified FPS
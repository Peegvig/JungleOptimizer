import time
import pygame
import sys
import random
from walls import *
from characters import *
from util import *

class JungleOptimizer():
    
    def __init__(self, window_width, window_height, world_height, world_width, fps, sound=False):
        
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

        #TODO: define player

        self.background_color = (181, 101, 29)
        self.wall_color = (1, 50, 32)
        self.border_color = (255, 0, 0)
        
        self.announcement_font = pygame.font.SysFont(None, 100)
        
        #TODO: define other variables
        
        self.score = 0


    def fill_background(self):

        self.screen.fill(self.background_color)

        #TODO: Set champ stats

        score_surface = self.font.render(f"Score: {self.score}", True, (0, 0, 0))
        self.screen.blit(score_surface, (10, 10))

    def step(self):
        print("Jungling step")
        self.fill_background()
        time.sleep(1)

        pygame.display.flip() # Updates display
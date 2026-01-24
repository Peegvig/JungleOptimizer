import random
import pygame
import math
from util import *

class Player:

    def __init__(self, world_width, world_height, walls):
        self.size = 50
        self.x = world_width//2 - 200
        self.y = world_height//2
        self.speed = 5

        while True: #make it so u dont spawn in wall

            self.rect = pygame.Rect(self.x, self.y, self.size, self.size)
            
            if check_collision(self.rect, walls):
                self.x = random.randint(-5, 5)
                self.y = random.randint(-5, 5)
            else:
                break
            
        self.score = 0
        
        self.images = pygame.transform.scale(pygame.image.load("images/amumu.png"), (self.size,self.size))

    def draw(self, screen, camera_x, camera_y):
        screen.blit(self.images, (self.x - camera_x, self.y - camera_y))

class Blue:

    def __init__(self,world_width, world_height, size=50, speed=1):
        self.size = size
        self.world_width = world_width
        self.world_height = world_height
        self.speed = speed
        self.x = world_width//2 + 200
        self.y = world_height//2 
  
        self.images = pygame.transform.scale(pygame.image.load("images/blue.png"), (self.size,self.size))
        self.rect = pygame.Rect(0, 0, self.size, self.size)
        self.rect.center = (self.x, self.y)
    
    def move():
        pass
        #TODO
    
    def draw(self, screen, camera_x, camera_y):
        screen.blit(self.images, (self.x - camera_x, self.y - camera_y))
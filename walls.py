import pygame

walls_1 = [
            pygame.Rect(200, 200, 400, 50),  # A horizontal wall
            # pygame.Rect(850, 500, 50, 400),  # A vertical wall
            pygame.Rect(1000, 1000, 300, 50), # Another horizontal wall
            # Add more walls as needed
        ]

walls_2 = [
    pygame.Rect(150, 100, 400, 50),   # Top-left horizontal wall
    pygame.Rect(150, 500, 450, 50),   # Bottom-left horizontal wall
    pygame.Rect(550, 250, 50, 300),  # Left vertical wall connecting top and bottom
    pygame.Rect(700, 100, 350, 50),  # Top-right horizontal wall
    pygame.Rect(700, 550, 400, 50),  # Bottom-right horizontal wall
    pygame.Rect(1000, 150, 50, 450), # Right vertical wall connecting top and bottom
    pygame.Rect(350, 300, 400, 50),  # Central horizontal wall, creating a middle corridor
    # pygame.Rect(600, 400, 50, 300),  # Vertical wall on the right of the central corridor
]

walls_3 = [
    pygame.Rect(100, 100, 600, 50),  # Horizontal wall near the top
    pygame.Rect(100, 200, 50, 400),  # Vertical wall on the left
    pygame.Rect(600, 300, 400, 50),  # Horizontal wall in the center
    pygame.Rect(900, 100, 50, 400),  # Vertical wall near the right side
    pygame.Rect(400, 500, 50, 400),  # Vertical wall in the center
    pygame.Rect(300, 600, 400, 50),  # Horizontal wall near the bottom
    pygame.Rect(1200, 500, 50, 400),  # Vertical wall near the right bottom
]
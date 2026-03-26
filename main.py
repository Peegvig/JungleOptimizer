from game import JungleOptimizer

WINDOW_WIDTH, WINDOW_HEIGHT = 1200, 800
WORLD_WIDTH, WORLD_HEIGHT = 2048, 2048  # Match minimap size for proper wall scaling
FPS = 60

# Choose champion: "Amumu", "Lee_Sin", or "Elise"
game = JungleOptimizer(
    window_height=WINDOW_HEIGHT,
    window_width=WINDOW_WIDTH,
    world_height=WORLD_HEIGHT,
    world_width=WORLD_WIDTH,
    fps=FPS,
    champion="Amumu",  # Change this to "Lee_Sin" or "Elise" to play different champions
    sound=True
)

# Game loop

while True:
    game.step()
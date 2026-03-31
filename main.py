from game import JungleOptimizer

WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 720
WORLD_WIDTH, WORLD_HEIGHT = 10240, 10240  # True world size (2048 * 5 scale factor)
FPS = 60

# Choose champion: "Amumu", "Lee_Sin", or "Elise"
game = JungleOptimizer(
    window_height=WINDOW_HEIGHT,
    window_width=WINDOW_WIDTH,
    world_height=WORLD_HEIGHT,
    world_width=WORLD_WIDTH,
    fps=FPS,
    champion="Amumu",  # Change this to "Lee_Sin" or "Elise" to play different champions
)

# Game loop

while True:
    game.step()
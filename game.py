import time
import pygame
import sys
import random
import json
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

        # Create player champion based on selection
        self.champion_name = champion
        if champion.lower() == "amumu":
            self.player = Amumu(world_width, world_height)
        elif champion.lower() == "lee_sin":
            self.player = LeeSin(world_width, world_height)
        elif champion.lower() == "elise":
            self.player = Elise(world_width, world_height)
        else:
            # Default to Amumu if champion not found
            print(f"Champion '{champion}' not found. Defaulting to Amumu.")
            self.player = Amumu(world_width, world_height)

        # Create enemy Blue
        self.blue = Blue(world_width, world_height)

        # Camera position (centered on player at start)
        self.camera_x = self.player.x - self.window_width // 2
        self.camera_y = self.player.y - self.window_height // 2
        
        # Camera follow settings
        self.camera_following = False  # Only follow when SPACE is held

        # Zoom settings
        self.zoom = 1.0  # 1.0 = 100% (no zoom)
        self.min_zoom = 0.3  # 30% zoom out
        self.max_zoom = 3.0  # 300% zoom in
        self.zoom_speed = 0.1  # Amount to change zoom per scroll
        self.prev_zoom = 1.0  # Track previous zoom to adjust camera when zooming

        # Camera panning
        self.camera_pan_speed = 20  # Pixels per frame when panning with SHIFT+WASD
        self.shift_pressed = False

        # Right-click dragging
        self.right_mouse_pressed = False

        self.background_color = (181, 101, 29)
        self.wall_color = (1, 50, 32)
        self.border_color = (255, 0, 0)
        
        # Load walls from JSON
        self.walls = self.load_walls_from_json("walls.json")
        
        # Load backdrop image (optional - falls back to color if not found)
        try:
            self.backdrop = pygame.image.load("images/SRminimap4x.png")
            # Scale backdrop to be much bigger (3x the world size)
            backdrop_scale = 5
            self.backdrop = pygame.transform.scale(self.backdrop, (world_width * backdrop_scale, world_height * backdrop_scale))
        except:
            self.backdrop = None
        
        # Cache for scaled backdrop to avoid rescaling every frame
        self.scaled_backdrop = None
        self.cached_zoom = None
        
        # Cache for scaled character sprites
        self.scaled_player_image = None
        self.scaled_blue_image = None
        self.cached_player_size = None
        self.cached_blue_size = None
        self.announcement_font = pygame.font.SysFont(None, 100)
        
        self.score = 0

    def load_walls_from_json(self, filename):
        """Load wall polygons from JSON file"""
        walls = []
        collision_rects = []
        wall_scale = 5  # Scale walls to match backdrop scale
        try:
            with open(filename, "r") as f:
                walls_data = json.load(f)
            
            if isinstance(walls_data, list):
                for polygon_coords in walls_data:
                    if isinstance(polygon_coords, list) and len(polygon_coords) >= 3:
                        # Convert coordinates to a list of (x, y) tuples for pygame rendering
                        coords = []
                        xs = []
                        ys = []
                        for coord in polygon_coords:
                            if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                                scaled_x = coord[0] * wall_scale
                                scaled_y = coord[1] * wall_scale
                                coords.append((scaled_x, scaled_y))
                                xs.append(scaled_x)
                                ys.append(scaled_y)
                        
                        if len(coords) >= 3:
                            walls.append(coords)
                            
                            # Create bounding box rect for collision detection
                            if xs and ys:
                                min_x = min(xs)
                                max_x = max(xs)
                                min_y = min(ys)
                                max_y = max(ys)
                                
                                width = max_x - min_x
                                height = max_y - min_y
                                
                                if width > 0 and height > 0:
                                    wall_rect = pygame.Rect(min_x, min_y, width, height)
                                    collision_rects.append(wall_rect)
                
                print(f"✓ Loaded {len(walls)} walls from {filename}")
            else:
                print(f"✗ Unexpected wall data format in {filename}")
        except FileNotFoundError:
            print(f"✗ Wall file {filename} not found")
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing {filename}: {e}")
        except Exception as e:
            print(f"✗ Error loading walls: {e}")
        
        # Store both visual polygons and collision rects
        self.wall_polygons = walls
        return collision_rects


    def fill_background(self):

        # Update camera to follow player only if holding SPACE
        if self.camera_following:
            self.camera_x = self.player.x - (self.window_width // 2) / self.zoom
            self.camera_y = self.player.y - (self.window_height // 2) / self.zoom

        # Helper function to convert world coordinates to screen coordinates with zoom
        def world_to_screen(world_x, world_y):
            screen_x = (world_x - self.camera_x) * self.zoom
            screen_y = (world_y - self.camera_y) * self.zoom
            return screen_x, screen_y

        # Draw backdrop image or fallback to color
        if self.backdrop:
            # Only rescale backdrop if zoom level has changed
            if self.scaled_backdrop is None or self.cached_zoom != self.zoom:
                scaled_width = int(self.backdrop.get_width() * self.zoom)
                scaled_height = int(self.backdrop.get_height() * self.zoom)
                self.scaled_backdrop = pygame.transform.scale(self.backdrop, (scaled_width, scaled_height))
                self.cached_zoom = self.zoom
            
            offset_x = int((-self.camera_x) * self.zoom)
            offset_y = int((-self.camera_y) * self.zoom)
            self.screen.blit(self.scaled_backdrop, (offset_x, offset_y))
        else:
            self.screen.fill(self.background_color)

        # Draw walls (scaled by zoom)
        if hasattr(self, 'wall_polygons') and self.wall_polygons:
            for wall_polygon in self.wall_polygons:
                # Convert world coordinates to screen coordinates for all vertices
                screen_polygon = []
                for x, y in wall_polygon:
                    screen_x, screen_y = world_to_screen(x, y)
                    screen_polygon.append((int(screen_x), int(screen_y)))
                
                # Draw filled polygon and outline
                if len(screen_polygon) >= 3:
                    pygame.draw.polygon(self.screen, self.wall_color, screen_polygon)
                    pygame.draw.polygon(self.screen, (0, 100, 0), screen_polygon, 2)

        # Draw player and enemies (scaled by zoom)
        screen_x, screen_y = world_to_screen(self.player.x, self.player.y)
        player_radius = self.player.radius * self.zoom
        if self.player.images:
            # Cache scaled player image to avoid rescaling every frame
            if self.scaled_player_image is None or self.cached_player_size != int(player_radius * 2):
                self.scaled_player_image = pygame.transform.scale(self.player.images, (int(player_radius * 2), int(player_radius * 2)))
                self.cached_player_size = int(player_radius * 2)
            self.screen.blit(self.scaled_player_image, (int(screen_x - player_radius), int(screen_y - player_radius)))
        else:
            pygame.draw.circle(self.screen, (255, 0, 0), (int(screen_x), int(screen_y)), int(player_radius))
        
        screen_x, screen_y = world_to_screen(self.blue.x, self.blue.y)
        blue_radius = self.blue.radius * self.zoom
        if self.blue.images:
            # Cache scaled blue image to avoid rescaling every frame
            if self.scaled_blue_image is None or self.cached_blue_size != int(blue_radius * 2):
                self.scaled_blue_image = pygame.transform.scale(self.blue.images, (int(blue_radius * 2), int(blue_radius * 2)))
                self.cached_blue_size = int(blue_radius * 2)
            self.screen.blit(self.scaled_blue_image, (int(screen_x - blue_radius), int(screen_y - blue_radius)))
        else:
            pygame.draw.circle(self.screen, (0, 0, 255), (int(screen_x), int(screen_y)), int(blue_radius))

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
        
        # Display zoom level
        zoom_percentage = int(self.zoom * 100)
        zoom_surface = self.font.render(f"Zoom: {zoom_percentage}%", True, (255, 255, 0))
        self.screen.blit(zoom_surface, (10, 170))
        
        # Display FPS counter in top right
        fps = int(self.clock.get_fps())
        fps_surface = self.font.render(f"FPS: {fps}", True, (0, 255, 255))
        fps_rect = fps_surface.get_rect()
        fps_rect.topright = (self.window_width - 10, 10)
        self.screen.blit(fps_surface, fps_rect)

    def step(self):

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click - helper to get coordinates
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x / self.zoom + self.camera_x
                    world_y = mouse_y / self.zoom + self.camera_y
                    print(f"Left-clicked at: x={world_x:.1f}, y={world_y:.1f}")
                elif event.button == 3:  # Right click pressed
                    self.right_mouse_pressed = True
                    # Convert screen position to world position
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x / self.zoom + self.camera_x
                    world_y = mouse_y / self.zoom + self.camera_y
                    self.player.set_target(world_x, world_y)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:  # Right click released
                    self.right_mouse_pressed = False
            elif event.type == pygame.MOUSEMOTION:
                # Update target while right-clicking and dragging
                if self.right_mouse_pressed:
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x / self.zoom + self.camera_x
                    world_y = mouse_y / self.zoom + self.camera_y
                    self.player.set_target(world_x, world_y)
            elif event.type == pygame.MOUSEWHEEL:
                # Mouse wheel zoom - zoom around the mouse cursor position
                mouse_x, mouse_y = pygame.mouse.get_pos()
                
                # Calculate world position that the mouse is pointing at before zoom
                mouse_world_x = mouse_x / self.zoom + self.camera_x
                mouse_world_y = mouse_y / self.zoom + self.camera_y
                
                # Apply zoom
                if event.y > 0:  # Scroll up = zoom in
                    self.zoom = min(self.zoom + self.zoom_speed, self.max_zoom)
                elif event.y < 0:  # Scroll down = zoom out
                    self.zoom = max(self.zoom - self.zoom_speed, self.min_zoom)
                
                # Adjust camera so the mouse still points at the same world position
                self.camera_x = mouse_world_x - mouse_x / self.zoom
                self.camera_y = mouse_world_y - mouse_y / self.zoom
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                    self.shift_pressed = True
                elif event.key == pygame.K_SPACE:
                    # Snap camera to player when SPACE is pressed
                    self.camera_x = self.player.x - self.window_width // 2
                    self.camera_y = self.player.y - self.window_height // 2
                    self.camera_following = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
                    self.shift_pressed = False
                elif event.key == pygame.K_SPACE:
                    self.camera_following = False
                # elif event.key == pygame.K_a:
                #     self.player.cast_auto_attack()
                elif event.key == pygame.K_q:
                    self.player.cast_q()
                elif event.key == pygame.K_w:
                    self.player.cast_w()
                elif event.key == pygame.K_e:
                    self.player.cast_e()

        # Update target continuously while right-click is held (for camera-locked dragging)
        if self.right_mouse_pressed:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            world_x = mouse_x / self.zoom + self.camera_x
            world_y = mouse_y / self.zoom + self.camera_y
            self.player.set_target(world_x, world_y)

        # Handle continuous camera panning with SHIFT + Arrow Keys
        if self.shift_pressed:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_UP]:  # Pan up
                self.camera_y -= self.camera_pan_speed / self.zoom
            if keys[pygame.K_DOWN]:  # Pan down
                self.camera_y += self.camera_pan_speed / self.zoom
            if keys[pygame.K_LEFT]:  # Pan left
                self.camera_x -= self.camera_pan_speed / self.zoom
            if keys[pygame.K_RIGHT]:  # Pan right
                self.camera_x += self.camera_pan_speed / self.zoom
            
            # Disable camera following when panning manually
            self.camera_following = False

        # Update champion movement and cooldowns
        self.player.update_movement(collide_with=self.blue, walls=self.walls)
        self.blue.update_movement(collide_with=self.player, walls=self.walls)
        self.player.update_cooldowns()

        self.fill_background()

        pygame.display.flip() # Updates display
        self.clock.tick(self.fps)  # Cap framerate at specified FPS
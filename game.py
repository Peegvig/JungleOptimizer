import time
import pygame
import sys
import random
import json
import math
from characters import *
from util import *

class JungleOptimizer():
    
    def __init__(self, window_width, window_height, world_height, world_width, fps, champion="Amumu"):
        
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

        # Camera follow settings
        self.camera_following = False  # Only follow when SPACE is held

        # Zoom settings
        self.base_zoom = 0.36  # Internal zoom factor that corresponds to 100% display
        self.zoom = self.base_zoom  # Default zoom (100%)
        self.min_zoom = 0.10  # ~28% display
        self.max_zoom = 1.08  # 300% display
        self.zoom_speed = 0.036  # Zoom increment per scroll step
        self.prev_zoom = self.base_zoom  # Track previous zoom to adjust camera when zooming

        # Camera position (centered on player at start)
        self.camera_x = self.player.x - (self.window_width // 2) / self.zoom
        self.camera_y = self.player.y - (self.window_height // 2) / self.zoom

        # Camera panning
        self.camera_pan_speed = 20  # Pixels per frame when panning with SHIFT+WASD
        self.shift_pressed = False

        # Right-click dragging
        self.right_mouse_pressed = False
        self.right_hold_timer = 0.0  # Throttle right-click-held updates
        self.RIGHT_HOLD_INTERVAL = 0.25  # Update 4 times per second

        self.background_color = (181, 101, 29)
        self.wall_color = (1, 50, 32)
        self.border_color = (255, 0, 0)
        
        # Load walls from JSON
        self.walls = self.load_walls_from_json("walls.json")
        
        # Give Blue the wall data for A* pathfinding
        self.blue.set_walls(self.wall_polygons, self.wall_bounds)
        
        # Give player the wall data for A* pathfinding
        self.player.set_walls(self.wall_polygons, self.wall_bounds)
        
        # Eagerly build the shared PathGrid so first click doesn't lag
        print("Building pathfinding grid (first time may take a moment)...")
        self.pathgrid = PathGrid(
            world_width, world_height,
            self.wall_polygons, self.wall_bounds,
            47, cell_size=50  # pathing_radius shared by player and Blue
        )
        print("Pathfinding grid ready.")
        self.player._pathfinder = self.pathgrid
        self.blue._pathfinder = self.pathgrid
        
        # Click marker (green circle like League)
        self.click_marker = None  # (x, y) world coords or None
        
        # Load backdrop image (optional - falls back to color if not found)
        try:
            self.backdrop = pygame.image.load("images/SRminimap4x.png")
            # Scale backdrop to match world dimensions (4x already has 5x scale built in)
            self.backdrop = pygame.transform.scale(self.backdrop, (world_width, world_height))
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
        wall_scale = 16000 / 2048  # Scale walls to match backdrop scale
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
        except FileNotFoundError:
            print(f"[ERROR] Wall file {filename} not found")
        except json.JSONDecodeError as e:
            print(f"[ERROR] Error parsing {filename}: {e}")
        except Exception as e:
            print(f"[ERROR] Error loading walls: {e}")
        
        # Store both visual polygons and collision rects
        self.wall_polygons = walls
        
        # Pre-compute bounding boxes for frustum culling
        self.wall_bounds = []
        for polygon in walls:
            xs = [x for x, y in polygon]
            ys = [y for x, y in polygon]
            if xs and ys:
                self.wall_bounds.append((min(xs), max(xs), min(ys), max(ys)))
            else:
                self.wall_bounds.append(None)
        
        return collision_rects
    
    def debug_print_walls(self):
        """Print wall bounds for debugging"""
        if self.walls:
            print(f"\\n=== WALL BOUNDS ===")
            for i, wall in enumerate(self.walls[:5]):  # Print first 5
                print(f"  Wall {i}: ({wall.left}, {wall.top}) -> ({wall.right}, {wall.bottom}) size=({wall.width}x{wall.height})")
            print(f"  ... and {len(self.walls) - 5} more walls")


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

        # Draw walls (scaled by zoom) - outline only, on-screen only for better performance
        if hasattr(self, 'wall_polygons') and self.wall_polygons:
            # Calculate camera bounds for frustum culling
            cam_left = self.camera_x
            cam_right = self.camera_x + self.window_width / self.zoom
            cam_top = self.camera_y
            cam_bottom = self.camera_y + self.window_height / self.zoom
            
            for i, wall_polygon in enumerate(self.wall_polygons):
                # Use pre-computed bounds for quick frustum culling
                if i < len(self.wall_bounds) and self.wall_bounds[i]:
                    min_x, max_x, min_y, max_y = self.wall_bounds[i]
                    # Skip if wall is completely off-screen
                    if max_x < cam_left or min_x > cam_right or max_y < cam_top or min_y > cam_bottom:
                        continue
                
                # Convert world coordinates to screen coordinates for all vertices
                screen_polygon = []
                for x, y in wall_polygon:
                    screen_x, screen_y = world_to_screen(x, y)
                    screen_polygon.append((int(screen_x), int(screen_y)))
                
                # Draw outline only with thicker border (faster than filled)
                if len(screen_polygon) >= 3:
                    pygame.draw.polygon(self.screen, (0, 100, 0), screen_polygon, 3)

        # Draw leash range circle (behind sprites)
        self.draw_leash_circle(self.blue, world_to_screen)

        # Draw click marker (green circle at right-click destination)
        if self.click_marker is not None:
            mx, my = world_to_screen(self.click_marker[0], self.click_marker[1])
            marker_radius = max(int(12 * self.zoom), 4)
            marker_surface = pygame.Surface((marker_radius * 2 + 2, marker_radius * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(marker_surface, (0, 255, 0, 200), (marker_radius + 1, marker_radius + 1), marker_radius, 2)
            pygame.draw.circle(marker_surface, (0, 255, 0, 100), (marker_radius + 1, marker_radius + 1), max(marker_radius // 3, 2))
            self.screen.blit(marker_surface, (int(mx) - marker_radius - 1, int(my) - marker_radius - 1))

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

        # Draw health bars above characters
        self.draw_health_bar(self.player, world_to_screen, is_monster=False)
        self.draw_health_bar(self.blue, world_to_screen, is_monster=True)

        # Draw attack animation bar above player's health bar
        self.draw_attack_bar(self.player, world_to_screen)
        self.draw_blue_attack_bar(self.blue, world_to_screen)

        # Draw patience bar below Blue's health bar
        self.draw_patience_bar(self.blue, world_to_screen)

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
        zoom_percentage = int((self.zoom / self.base_zoom) * 100)
        zoom_surface = self.font.render(f"Zoom: {zoom_percentage}%", True, (255, 255, 0))
        self.screen.blit(zoom_surface, (10, 170))
        
        # Display FPS counter in top right
        fps = int(self.clock.get_fps())
        fps_surface = self.font.render(f"FPS: {fps}", True, (0, 255, 255))
        fps_rect = fps_surface.get_rect()
        fps_rect.topright = (self.window_width - 10, 10)
        self.screen.blit(fps_surface, fps_rect)

    def draw_attack_bar(self, unit, world_to_screen):
        """Draw an attack animation progress bar above the unit's health bar.
        Shows windup phase, committed phase, and a tick mark at the windup threshold."""
        total_attack_time = 1.0 / unit.attack_speed
        windup_time = total_attack_time * unit.ATTACK_WINDUP_PERCENT

        # Determine current progress ratio (0.0 to 1.0 over the full attack time)
        if unit.attack_winding_up:
            progress = unit.attack_windup_elapsed / total_attack_time
        elif unit.attack_committed:
            # Committed: windup is done, count forward from windup% to 100%
            elapsed_commit = (total_attack_time - windup_time) - unit.attack_commit_timer
            progress = (windup_time + elapsed_commit) / total_attack_time
        else:
            progress = 0.0

        # Only draw when there's an active attack animation
        if progress <= 0.0:
            return

        progress = min(progress, 1.0)

        screen_x, screen_y = world_to_screen(unit.x, unit.y)
        unit_radius = unit.radius * self.zoom

        # Match health bar width; place above it
        bar_width = max(int(unit.radius * 4.4 * self.zoom), 60)
        bar_height = max(int(8 * self.zoom), 4)
        border_thickness = max(int(2 * self.zoom), 1)
        hp_bar_height = max(int(12 * self.zoom), 6)
        hp_border = max(int(3 * self.zoom), 2)
        gap = max(int(4 * self.zoom), 2)

        bar_x = int(screen_x - bar_width / 2)
        # Position above the health bar (health bar y minus gap minus this bar)
        hp_bar_y = int(screen_y - unit_radius - hp_bar_height - max(int(12 * self.zoom), 8))
        bar_y = hp_bar_y - hp_border - gap - bar_height - border_thickness * 2

        fill_width = int(bar_width * progress)

        # Color: orange during windup, green once committed
        if unit.attack_winding_up:
            fill_color = (255, 165, 0)  # Orange - can still cancel
        else:
            fill_color = (0, 200, 255)  # Cyan - committed, damage locked in

        # Draw border
        pygame.draw.rect(self.screen, (10, 10, 10),
                         (bar_x - border_thickness, bar_y - border_thickness,
                          bar_width + border_thickness * 2, bar_height + border_thickness * 2))
        # Draw background
        pygame.draw.rect(self.screen, (40, 40, 40),
                         (bar_x, bar_y, bar_width, bar_height))
        # Draw filled progress
        if fill_width > 0:
            pygame.draw.rect(self.screen, fill_color,
                             (bar_x, bar_y, fill_width, bar_height))

        # Draw tick mark at windup threshold (23.384%)
        tick_x = bar_x + int(bar_width * unit.ATTACK_WINDUP_PERCENT)
        tick_extend = max(int(3 * self.zoom), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (tick_x, bar_y - tick_extend),
                         (tick_x, bar_y + bar_height + tick_extend), 2)

    def draw_blue_attack_bar(self, unit, world_to_screen):
        """Draw Blue's attack progress bar above its health bar.
        Shows windup phase (orange) up to 32.1%, then cooldown phase (cyan) to 100%."""
        # Show bar during windup OR during post-windup cooldown
        if not unit.is_attacking and unit.attack_cooldown <= 0:
            return

        total_attack_time = 1.0 / unit.attack_speed
        if unit.is_attacking and unit.attack_winding_up:
            # Windup phase: progress goes from 0% to 32.1%
            progress = unit.attack_windup_elapsed / total_attack_time
        elif unit.attack_cooldown > 0 and unit.attack_cooldown_total > 0:
            # Post-windup cooldown: progress continues from 32.1% to 100%
            cooldown_progress = 1.0 - (unit.attack_cooldown / unit.attack_cooldown_total)
            progress = unit.ATTACK_WINDUP_PERCENT + (1.0 - unit.ATTACK_WINDUP_PERCENT) * cooldown_progress
        else:
            return
        progress = max(0.0, min(progress, 1.0))

        screen_x, screen_y = world_to_screen(unit.x, unit.y)
        unit_radius = unit.radius * self.zoom

        bar_width = max(int(unit.radius * 4.4 * self.zoom), 60)
        bar_height = max(int(8 * self.zoom), 4)
        border_thickness = max(int(2 * self.zoom), 1)
        hp_bar_height = max(int(12 * self.zoom), 6)
        hp_border = max(int(3 * self.zoom), 2)
        gap = max(int(4 * self.zoom), 2)

        bar_x = int(screen_x - bar_width / 2)
        hp_bar_y = int(screen_y - unit_radius - hp_bar_height - max(int(12 * self.zoom), 8))
        bar_y = hp_bar_y - hp_border - gap - bar_height - border_thickness * 2

        # Border
        pygame.draw.rect(self.screen, (10, 10, 10),
                         (bar_x - border_thickness, bar_y - border_thickness,
                          bar_width + border_thickness * 2, bar_height + border_thickness * 2))
        # Background
        pygame.draw.rect(self.screen, (40, 40, 40),
                         (bar_x, bar_y, bar_width, bar_height))

        # Draw windup portion (orange, 0% to 32.1%)
        windup_fill = min(progress, unit.ATTACK_WINDUP_PERCENT)
        windup_px = int(bar_width * windup_fill)
        if windup_px > 0:
            pygame.draw.rect(self.screen, (255, 165, 0),
                             (bar_x, bar_y, windup_px, bar_height))

        # Draw cooldown portion (cyan, 32.1% to current progress)
        if progress > unit.ATTACK_WINDUP_PERCENT:
            cooldown_start_px = int(bar_width * unit.ATTACK_WINDUP_PERCENT)
            cooldown_end_px = int(bar_width * progress)
            cooldown_width = cooldown_end_px - cooldown_start_px
            if cooldown_width > 0:
                pygame.draw.rect(self.screen, (0, 200, 255),
                                 (bar_x + cooldown_start_px, bar_y, cooldown_width, bar_height))

        # Draw tick mark at windup threshold (32.1%)
        tick_x = bar_x + int(bar_width * unit.ATTACK_WINDUP_PERCENT)
        tick_extend = max(int(3 * self.zoom), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (tick_x, bar_y - tick_extend),
                         (tick_x, bar_y + bar_height + tick_extend), 2)

    def draw_health_bar(self, unit, world_to_screen, is_monster=False):
        """Draw a League of Legends style health bar above a unit.
        
        Args:
            unit: The character/monster to draw the health bar for
            world_to_screen: Coordinate conversion function
            is_monster: If True, show HP number text (for jungle monsters)
        """
        if not hasattr(unit, 'hp') or not hasattr(unit, 'max_hp'):
            return
        
        screen_x, screen_y = world_to_screen(unit.x, unit.y)
        unit_radius = unit.radius * self.zoom
        
        # Health bar dimensions (scale with zoom) - 2x size
        bar_width = max(int(unit.radius * 4.4 * self.zoom), 60)
        bar_height = max(int(12 * self.zoom), 6)
        border_thickness = max(int(3 * self.zoom), 2)
        
        # Position above the character sprite
        bar_x = int(screen_x - bar_width / 2)
        bar_y = int(screen_y - unit_radius - bar_height - max(int(12 * self.zoom), 8))
        
        hp_ratio = max(0, min(1, unit.hp / unit.max_hp))
        fill_width = int(bar_width * hp_ratio)
        
        # Colors
        bg_color = (30, 30, 30)
        border_color = (10, 10, 10)
        
        # Fixed colors: monsters always red, players always green
        if is_monster:
            bar_color = (200, 30, 30)   # Red for monsters
        else:
            bar_color = (50, 205, 50)   # Green for players
        
        # For monsters: draw HP number ABOVE the attack bar (or health bar if no attack bar)
        if is_monster:
            hp_font_size = max(int(32 * self.zoom), 20)
            if not hasattr(self, '_hp_font_cache') or self._hp_font_cache_size != hp_font_size:
                self._hp_font_cache = pygame.font.SysFont(None, hp_font_size)
                self._hp_font_cache_size = hp_font_size
            hp_text = self._hp_font_cache.render(f"{int(unit.hp)}/{int(unit.max_hp)}", True, (255, 255, 255))
            # Offset text above the attack bar area so they don't overlap
            atk_bar_height = max(int(8 * self.zoom), 4)
            atk_border = max(int(2 * self.zoom), 1)
            atk_gap = max(int(4 * self.zoom), 2)
            text_bottom = bar_y - border_thickness - atk_gap - atk_bar_height - atk_border * 2 - 1
            text_rect = hp_text.get_rect(centerx=int(screen_x), bottom=text_bottom)
            # Draw text shadow for readability
            shadow = self._hp_font_cache.render(f"{int(unit.hp)}/{int(unit.max_hp)}", True, (0, 0, 0))
            self.screen.blit(shadow, (text_rect.x + 1, text_rect.y + 1))
            self.screen.blit(hp_text, text_rect)
        
        # Draw border
        pygame.draw.rect(self.screen, border_color,
                         (bar_x - border_thickness, bar_y - border_thickness,
                          bar_width + border_thickness * 2, bar_height + border_thickness * 2))
        # Draw background (depleted health)
        pygame.draw.rect(self.screen, bg_color,
                         (bar_x, bar_y, bar_width, bar_height))
        # Draw filled health
        if fill_width > 0:
            pygame.draw.rect(self.screen, bar_color,
                             (bar_x, bar_y, fill_width, bar_height))
        
        # Draw segment ticks (every 100 HP for players, every 1000 HP for monsters)
        hp_per_tick = 1000 if is_monster else 100
        num_ticks = int(unit.max_hp / hp_per_tick)
        if num_ticks > 1 and num_ticks <= 50:
            for i in range(1, num_ticks):
                tick_x = bar_x + int(bar_width * (i * hp_per_tick / unit.max_hp))
                pygame.draw.line(self.screen, (0, 0, 0),
                                 (tick_x, bar_y), (tick_x, bar_y + bar_height), 1)

    def draw_leash_circle(self, unit, world_to_screen):
        """Draw the leash range circle around the monster's spawn point."""
        show_circle = False
        if hasattr(unit, 'leash_circle_visible') and unit.leash_circle_visible:
            show_circle = True
        if hasattr(unit, 'reset_state') and unit.reset_state != unit.RESET_NONE:
            show_circle = True
        if hasattr(unit, 'patience_recovering') and unit.patience_recovering:
            show_circle = True
        if not show_circle:
            return
        
        screen_x, screen_y = world_to_screen(unit.spawn_x, unit.spawn_y)
        leash_screen_radius = int(unit.leash_range * self.zoom)
        
        # Color based on state
        if hasattr(unit, 'reset_state') and unit.reset_state == unit.RESET_HARD:
            circle_color = (200, 50, 50)  # Red during hard reset
        elif hasattr(unit, 'patience') and unit.patience < 30:
            circle_color = (220, 120, 40)  # Orange when patience low
        else:
            circle_color = (180, 180, 180)  # Light gray normally
        
        thickness = max(int(3 * self.zoom), 2)
        pygame.draw.circle(self.screen, circle_color,
                           (int(screen_x), int(screen_y)), leash_screen_radius, thickness)

    def draw_patience_bar(self, unit, world_to_screen):
        """Draw patience bar below the health bar (only when aggroed or resetting)."""
        if not hasattr(unit, 'patience') or not hasattr(unit, 'patience_max'):
            return
        # Only show when relevant
        show = (unit.aggro or unit.reset_state != unit.RESET_NONE or unit.patience_recovering)
        if not show:
            return
        
        screen_x, screen_y = world_to_screen(unit.x, unit.y)
        unit_radius = unit.radius * self.zoom
        
        bar_width = max(int(unit.radius * 4.4 * self.zoom), 60)
        bar_height = max(int(8 * self.zoom), 4)
        border_thickness = max(int(2 * self.zoom), 1)
        hp_bar_height = max(int(12 * self.zoom), 6)
        hp_border = max(int(3 * self.zoom), 2)
        gap = max(int(4 * self.zoom), 2)
        
        # Position below the health bar
        hp_bar_y = int(screen_y - unit_radius - hp_bar_height - max(int(12 * self.zoom), 8))
        bar_x = int(screen_x - bar_width / 2)
        bar_y = hp_bar_y + hp_bar_height + hp_border + gap
        
        patience_ratio = max(0, min(1, unit.patience / unit.patience_max))
        fill_width = int(bar_width * patience_ratio)
        
        # Color: teal when high, orange when medium, red when low
        if patience_ratio > 0.5:
            bar_color = (0, 200, 200)  # Teal
        elif patience_ratio > 0.25:
            bar_color = (255, 165, 0)  # Orange
        else:
            bar_color = (200, 30, 30)  # Red
        
        # Draw border
        pygame.draw.rect(self.screen, (10, 10, 10),
                         (bar_x - border_thickness, bar_y - border_thickness,
                          bar_width + border_thickness * 2, bar_height + border_thickness * 2))
        # Draw background
        pygame.draw.rect(self.screen, (40, 40, 40),
                         (bar_x, bar_y, bar_width, bar_height))
        # Draw filled patience
        if fill_width > 0:
            pygame.draw.rect(self.screen, bar_color,
                             (bar_x, bar_y, fill_width, bar_height))

    def step(self):

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click - helper to get coordinates
                    pass
                elif event.button == 3:  # Right click pressed
                    self.right_mouse_pressed = True
                    # Convert screen position to world position
                    mouse_x, mouse_y = event.pos
                    world_x = mouse_x / self.zoom + self.camera_x
                    world_y = mouse_y / self.zoom + self.camera_y
                    
                    # Check if clicking on Blue (within its gameplay radius)
                    dx = world_x - self.blue.x
                    dy = world_y - self.blue.y
                    if math.sqrt(dx**2 + dy**2) <= self.blue.radius:
                        self.player.set_attack_target(self.blue)
                    else:
                        # Snap to nearest walkable position if clicking in a wall
                        world_x, world_y = self.pathgrid.snap_to_walkable(world_x, world_y)
                        self.player.set_target(world_x, world_y)
                        self.click_marker = (world_x, world_y)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:  # Right click released
                    self.right_mouse_pressed = False
            elif event.type == pygame.MOUSEMOTION:
                # Motion events are ignored for right-click hold; throttled update below handles it
                pass
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

        # Update target while right-click is held, throttled to 4 times per second
        if self.right_mouse_pressed:
            self.right_hold_timer += 1.0 / self.fps
            if self.right_hold_timer >= self.RIGHT_HOLD_INTERVAL:
                self.right_hold_timer = 0.0
                mouse_x, mouse_y = pygame.mouse.get_pos()
                world_x = mouse_x / self.zoom + self.camera_x
                world_y = mouse_y / self.zoom + self.camera_y
                # Check if cursor is over Blue — start attacking
                dx = world_x - self.blue.x
                dy = world_y - self.blue.y
                if math.sqrt(dx**2 + dy**2) <= self.blue.radius:
                    if self.player.attack_target is not self.blue:
                        self.player.set_attack_target(self.blue)
                elif self.player.attack_target is None:
                    # Snap to nearest walkable position if clicking in a wall
                    world_x, world_y = self.pathgrid.snap_to_walkable(world_x, world_y)
                    # Only update move target if not auto-attacking
                    self.player.set_target(world_x, world_y)
                    self.click_marker = (world_x, world_y)
        else:
            self.right_hold_timer = 0.0

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

        # Update champion movement first (so entering attack range is detected this frame)
        self.player.update_movement(collide_with=self.blue, wall_polygons=self.wall_polygons, wall_bounds=self.wall_bounds)
        self.blue.update_movement(collide_with=self.player, wall_polygons=self.wall_polygons, wall_bounds=self.wall_bounds)

        # Update auto-attack (after movement so attack starts immediately on entering range)
        dt = 1.0 / self.fps

        # Clear click marker when player reaches destination or stops moving
        if self.click_marker is not None:
            dx = self.player.x - self.click_marker[0]
            dy = self.player.y - self.click_marker[1]
            if math.sqrt(dx*dx + dy*dy) < self.player.speed or not self.player.is_moving:
                self.click_marker = None

        damage = self.player.update_auto_attack(dt)
        if damage > 0:
            self.blue.hp = max(0, self.blue.hp - damage)
            # Trigger Blue aggro when the player deals damage
            self.blue.trigger_aggro(self.player)

        # Update Blue AI (chase and attack)
        blue_damage = self.blue.update_ai(dt)
        if blue_damage > 0:
            self.player.hp = max(0, self.player.hp - blue_damage)

        # Update cooldowns
        self.player.update_cooldowns()

        self.fill_background()

        pygame.display.flip() # Updates display
        self.clock.tick(self.fps)  # Cap framerate at specified FPS
import random
import pygame
import math
from util import *

class Champion:
    """Base class for all playable champions"""

    def __init__(self, world_width, world_height):
        self.size = 55
        self.x = 2135
        self.y = 4711
        
        self.world_width = world_width
        self.world_height = world_height
        
        # Base stats - override in subclasses
        self.speed = 5
        self.hp = 500
        self.max_hp = 500
        self.mana = 300
        self.max_mana = 300
        self.attack_damage = 55
        self.armor = 20
        
        self.score = 0

        # Circle-based positioning (x, y is now the CENTER of the circle)
        self.radius = self.size // 2  # Gameplay radius (hitbox for abilities/visuals)
        self.pathing_radius = 30  # Pathing radius (movement collision, smaller than gameplay)
        
        # Movement
        self.target_x = None
        self.target_y = None
        self.is_moving = False
        
        # Wall pass-through tag system
        self.can_pass_walls = False  # By default, units cannot pass walls
        self.wall_pass_tags = set()  # Set of tags that allow wall passing
        
        # Ability cooldowns (in frames)
        self.auto_attack_cooldown = 0
        self.q_cooldown = 0
        self.w_cooldown = 0
        self.e_cooldown = 0
        
        # Ability cooldown constants - override in subclasses
        self.AUTO_ATTACK_COOLDOWN = 15  # ~0.25 seconds
        self.Q_COOLDOWN = 60  # ~1 second
        self.W_COOLDOWN = 90  # ~1.5 seconds
        self.E_COOLDOWN = 120  # ~2 seconds
        
        # Auto-attack system
        self.attack_target = None  # The unit being auto-attacked
        self.attack_range = 125  # Edge-to-edge attack range
        self.attack_speed = 0.736  # Attacks per second
        self.attack_timer = 0.0  # Seconds until next attack is ready
        self.base_attack_damage_value = 57  # Damage per auto-attack
        
        # Attack canceling (windup/commit system)
        self.ATTACK_WINDUP_PERCENT = 0.23384  # 23.384% of attack time
        self.attack_winding_up = False  # True during windup phase
        self.attack_windup_elapsed = 0.0  # Time elapsed in current windup
        self.attack_committed = False  # True when damage is locked in
        self.attack_commit_timer = 0.0  # Time remaining until committed damage lands
        self.pending_attack_damage = 0  # Committed damage waiting to be dealt
        
        # Load champion image - override in subclasses
        self.images = None

    def set_target(self, target_x, target_y):
        """Set movement target position. Cancels attack if in windup phase.
        If attack is committed (past windup), damage still goes through."""
        self.target_x = target_x
        self.target_y = target_y
        self.is_moving = True
        
        if self.attack_winding_up:
            # Cancel attack during windup - no damage, can attack again
            self.attack_winding_up = False
            self.attack_windup_elapsed = 0.0
            self.attack_target = None
            self.attack_timer = 0.0
        else:
            # Clear attack target (committed damage still goes through)
            self.attack_target = None

    def set_attack_target(self, target_unit):
        """Set a unit to auto-attack. Will move toward it if out of range."""
        self.attack_target = target_unit
        # Start moving toward target immediately if not in range
        if not self.is_in_attack_range(target_unit):
            self.target_x = target_unit.x
            self.target_y = target_unit.y
            self.is_moving = True
        else:
            self.is_moving = False
            self.target_x = None
            self.target_y = None

    def is_in_attack_range(self, target):
        """Check if target is within attack range (edge-to-edge)."""
        dx = self.x - target.x
        dy = self.y - target.y
        center_distance = math.sqrt(dx**2 + dy**2)
        edge_distance = center_distance - self.radius - target.radius
        return edge_distance <= self.attack_range

    def update_auto_attack(self, dt):
        """Update auto-attack logic with windup/commit canceling.
        
        Attack phases:
        1. Windup (0% to 23.384%): Can be canceled by movement. No damage.
        2. Committed (23.384% to 100%): Damage locked in. Can move freely.
           Damage is dealt when the full attack time elapses.
        
        Args:
            dt: Delta time in seconds since last frame
            
        Returns:
            Damage dealt this frame (0 if none)
        """
        total_attack_time = 1.0 / self.attack_speed
        windup_time = total_attack_time * self.ATTACK_WINDUP_PERCENT
        damage = 0
        
        # Always tick down attack cooldown timer (even while moving or without target)
        if self.attack_timer > 0:
            self.attack_timer -= dt
        
        # Process committed phase countdown (damage already dealt at threshold)
        if self.attack_committed:
            self.attack_commit_timer -= dt
            if self.attack_commit_timer <= 0:
                self.attack_committed = False
        
        # No target - just return any committed damage
        if self.attack_target is None:
            return damage
        
        # Move toward target if out of range
        if not self.is_in_attack_range(self.attack_target):
            if self.attack_winding_up:
                # Cancel windup if target moved out of range
                self.attack_winding_up = False
                self.attack_windup_elapsed = 0.0
            self.target_x = self.attack_target.x
            self.target_y = self.attack_target.y
            self.is_moving = True
            return damage
        
        # In range - stop moving if not winding up or committed
        if not self.attack_winding_up and not self.attack_committed:
            self.is_moving = False
            self.target_x = None
            self.target_y = None
        
        # Wait for cooldown before starting new attack
        if self.attack_timer > 0:
            return damage
        
        # Start new attack if not already winding up or committed
        if not self.attack_winding_up and not self.attack_committed:
            self.attack_winding_up = True
            self.attack_windup_elapsed = 0.0
            self.is_moving = False
            self.target_x = None
            self.target_y = None
        
        # Continue/process windup (including newly started attacks)
        if self.attack_winding_up:
            self.attack_windup_elapsed += dt
            if self.attack_windup_elapsed >= windup_time:
                # Windup complete - deal damage immediately at threshold
                damage += self.base_attack_damage_value
                self.attack_winding_up = False
                self.attack_windup_elapsed = 0.0
                # Enter committed state (no pending damage, just animation remainder)
                self.attack_committed = True
                self.attack_commit_timer = total_attack_time - windup_time
                self.pending_attack_damage = 0
                # Set cooldown so next attack can't start until this attack period ends
                self.attack_timer = total_attack_time - windup_time
            return damage
        
        return damage

    def add_wall_pass_tag(self, tag):
        """Add a tag that allows this unit to pass through walls"""
        self.wall_pass_tags.add(tag)
    
    def remove_wall_pass_tag(self, tag):
        """Remove a wall pass tag"""
        self.wall_pass_tags.discard(tag)
    
    def has_wall_pass_tag(self, tag):
        """Check if this unit has a specific wall pass tag"""
        return tag in self.wall_pass_tags
    
    def can_pass_wall(self):
        """Check if this unit can currently pass through walls"""
        return len(self.wall_pass_tags) > 0

    def update_movement(self, collide_with=None, walls=None, wall_polygons=None, wall_bounds=None, can_pass_walls=False):
        """Update champion position towards target
        
        Args:
            collide_with: Another champion to check collision with
            walls: (Deprecated) List of wall bounding-box rectangles
            wall_polygons: List of polygon coordinate lists for accurate collision
            wall_bounds: List of (min_x, max_x, min_y, max_y) tuples for fast culling
            can_pass_walls: (Deprecated - use add_wall_pass_tag() instead)
        """
        if not self.is_moving or self.target_x is None or self.target_y is None:
            return
        
        # If we have an attack target and are already in range, stop moving immediately
        if self.attack_target and self.is_in_attack_range(self.attack_target):
            self.is_moving = False
            self.target_x = None
            self.target_y = None
            return
        
        # Calculate distance to target
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)
        
        # Check if reached target
        if distance < self.speed:
            self.x = self.target_x
            self.y = self.target_y
            self.is_moving = False
            self.target_x = None
            self.target_y = None
            return
        
        # Normalize direction and move
        if distance > 0:
            move_x = (dx / distance) * self.speed
            move_y = (dy / distance) * self.speed
            
            # Store old position in case we need to revert
            old_x = self.x
            old_y = self.y
            
            # Update position (x, y is center of circle)
            self.x += move_x
            self.y += move_y
            
            # Check collisions
            collision_detected = False
            collision_reason = ""
            
            # Check character collision
            if collide_with and self.check_collision(collide_with):
                collision_detected = True
                collision_reason = "character collision"
            
            # Check wall collision (unless unit can pass walls)
            if wall_polygons:
                if self.check_wall_collision(wall_polygons, wall_bounds):
                    collision_detected = True
                    collision_reason = "wall collision"
            
            # Revert if collision detected
            if collision_detected:
                self.x = old_x
                self.y = old_y
                return
            
            # After moving, check if we've entered attack range — stop early
            if self.attack_target and self.is_in_attack_range(self.attack_target):
                self.is_moving = False
                self.target_x = None
                self.target_y = None

    def check_wall_collision(self, wall_polygons, wall_bounds=None):
        """Check if champion circle collides with any wall polygons.
        Returns True if collision detected and unit cannot pass walls.
        Returns False if unit has wall pass tags or no collision occurs.
        """
        # If unit can pass walls, don't check collision
        if self.can_pass_wall():
            return False
        
        for i, polygon in enumerate(wall_polygons):
            # Fast bounding-box pre-filter
            if wall_bounds and i < len(wall_bounds) and wall_bounds[i]:
                min_x, max_x, min_y, max_y = wall_bounds[i]
                if (self.x + self.radius < min_x or self.x - self.radius > max_x or
                        self.y + self.radius < min_y or self.y - self.radius > max_y):
                    continue
            
            # Check if circle center is inside the polygon
            if point_in_polygon(self.x, self.y, polygon):
                return True
            
            # Check distance from circle center to each polygon edge (use pathing_radius for walls)
            n = len(polygon)
            for j in range(n):
                x1, y1 = polygon[j]
                x2, y2 = polygon[(j + 1) % n]
                if point_to_segment_distance(self.x, self.y, x1, y1, x2, y2) < self.pathing_radius:
                    return True
        
        return False

    def check_collision(self, other):
        """Check pathing collision with another unit.
        Uses pathing_radius: a unit's center cannot enter another unit's pathing radius.
        This allows units to partially overlap visually while still blocking movement.
        """
        dx = self.x - other.x
        dy = self.y - other.y
        distance = math.sqrt(dx**2 + dy**2)
        return distance < (self.pathing_radius + other.pathing_radius)

    def update_cooldowns(self):
        """Decrement all ability cooldowns"""
        if self.auto_attack_cooldown > 0:
            self.auto_attack_cooldown -= 1
        if self.q_cooldown > 0:
            self.q_cooldown -= 1
        if self.w_cooldown > 0:
            self.w_cooldown -= 1
        if self.e_cooldown > 0:
            self.e_cooldown -= 1

    def cast_auto_attack(self):
        """Handle auto attack ability - override in subclasses"""
        if self.auto_attack_cooldown <= 0:
            print("Auto Attack!")
            # TODO: Implement auto attack logic
            self.auto_attack_cooldown = self.AUTO_ATTACK_COOLDOWN
        else:
            print(f"Auto attack on cooldown")

    def cast_q(self):
        """Handle Q ability - override in subclasses"""
        if self.q_cooldown <= 0:
            print("Q Ability Cast!")
            # TODO: Implement Q ability logic
            self.q_cooldown = self.Q_COOLDOWN
        else:
            print(f"Q on cooldown")

    def cast_w(self):
        """Handle W ability - override in subclasses"""
        if self.w_cooldown <= 0:
            print("W Ability Cast!")
            # TODO: Implement W ability logic
            self.w_cooldown = self.W_COOLDOWN
        else:
            print(f"W on cooldown")

    def cast_e(self):
        """Handle E ability - override in subclasses"""
        if self.e_cooldown <= 0:
            print("E Ability Cast!")
            # TODO: Implement E ability logic
            self.e_cooldown = self.E_COOLDOWN
        else:
            print(f"E on cooldown")


class Amumu(Champion):
    """The Sad Mummy - Tank jungler"""

    def __init__(self, world_width, world_height):
        super().__init__(world_width, world_height)
        
        # Amumu stats
        self.speed = 3.35
        self.hp = 510
        self.max_hp = 510
        self.mana = 300
        self.max_mana = 300
        self.attack_damage = 55
        self.armor = 25
        
        # Amumu ability cooldowns
        self.Q_COOLDOWN = 60  # Bandage Toss
        self.W_COOLDOWN = 90  # Despair
        self.E_COOLDOWN = 120  # Tantrum
        
        # Amumu auto-attack stats
        self.attack_range = 125  # Edge-to-edge
        self.attack_speed = 0.736  # Attacks per second
        self.base_attack_damage_value = 57  # Damage per auto-attack
        
        # Load Amumu image
        self.images = pygame.transform.scale(
            pygame.image.load("images/amumuC.png"), 
            (self.size, self.size)
        )

    def cast_q(self):
        """Bandage Toss - Q ability"""
        if self.q_cooldown <= 0:
            self.mana -= 50  # Mana cost
            print("Bandage Toss! (Amumu Q)")
            # TODO: Implement Bandage Toss logic (projectile, stun on hit)
            self.q_cooldown = self.Q_COOLDOWN
        else:
            print(f"Q on cooldown: {self.q_cooldown} frames")

    def cast_w(self):
        """Despair - W ability"""
        if self.w_cooldown <= 0:
            self.mana -= 60
            print("Despair! (Amumu W)")
            # TODO: Implement Despair logic (AoE damage around Amumu)
            self.w_cooldown = self.W_COOLDOWN
        else:
            print(f"W on cooldown: {self.w_cooldown} frames")

    def cast_e(self):
        """Tantrum - E ability"""
        if self.e_cooldown <= 0:
            self.mana -= 40
            print("Tantrum! (Amumu E)")
            # TODO: Implement Tantrum logic (damage reduction + counter damage)
            self.e_cooldown = self.E_COOLDOWN
        else:
            print(f"E on cooldown: {self.e_cooldown} frames")


class LeeSin(Champion):
    """The Blind Monk - Skill-based jungler"""

    def __init__(self, world_width, world_height):
        super().__init__(world_width, world_height)
        
        # Lee Sin stats
        self.speed = 6
        self.hp = 520
        self.max_hp = 520
        self.mana = 200
        self.max_mana = 200
        self.attack_damage = 60
        self.armor = 22
        
        # Lee Sin ability cooldowns
        self.Q_COOLDOWN = 80  # Sonic Wave
        self.W_COOLDOWN = 70  # Safeguard
        self.E_COOLDOWN = 100  # Tempest
        
        # Load Lee Sin image
        self.images = pygame.transform.scale(
            pygame.image.load("images/lee_sin.png"), 
            (self.size, self.size)
        )

    def cast_q(self):
        """Sonic Wave - Q ability"""
        if self.q_cooldown <= 0:
            self.mana -= 55
            print("Sonic Wave! (Lee Sin Q)")
            # TODO: Implement Sonic Wave logic (skillshot projectile)
            self.q_cooldown = self.Q_COOLDOWN
        else:
            print(f"Q on cooldown: {self.q_cooldown} frames")

    def cast_w(self):
        """Safeguard - W ability"""
        if self.w_cooldown <= 0:
            self.mana -= 50
            print("Safeguard! (Lee Sin W)")
            # TODO: Implement Safeguard logic (shield, dash to target)
            self.w_cooldown = self.W_COOLDOWN
        else:
            print(f"W on cooldown: {self.w_cooldown} frames")

    def cast_e(self):
        """Tempest - E ability"""
        if self.e_cooldown <= 0:
            self.mana -= 65
            print("Tempest! (Lee Sin E)")
            # TODO: Implement Tempest logic (AoE slow)
            self.e_cooldown = self.E_COOLDOWN
        else:
            print(f"E on cooldown: {self.e_cooldown} frames")


class Elise(Champion):
    """The Spider Queen - Versatile jungler"""

    def __init__(self, world_width, world_height):
        super().__init__(world_width, world_height)
        
        # Elise stats
        self.speed = 5
        self.hp = 510
        self.max_hp = 510
        self.mana = 340
        self.max_mana = 340
        self.attack_damage = 53
        self.armor = 21
        
        # Elise ability cooldowns
        self.Q_COOLDOWN = 70  # Neurotoxin/Venomous Bite
        self.W_COOLDOWN = 100  # Volatile Spiderling/Skittering Frenzy
        self.E_COOLDOWN = 110  # Cocoon/Rappel
        
        # Load Elise image
        self.images = pygame.transform.scale(
            pygame.image.load("images/elise.png"), 
            (self.size, self.size)
        )

    def cast_q(self):
        """Neurotoxin/Venomous Bite - Q ability"""
        if self.q_cooldown <= 0:
            self.mana -= 60
            print("Neurotoxin! (Elise Q)")
            # TODO: Implement Neurotoxin logic (target damage)
            self.q_cooldown = self.Q_COOLDOWN
        else:
            print(f"Q on cooldown: {self.q_cooldown} frames")

    def cast_w(self):
        """Volatile Spiderling/Skittering Frenzy - W ability"""
        if self.w_cooldown <= 0:
            self.mana -= 70
            print("Volatile Spiderling! (Elise W)")
            # TODO: Implement Volatile Spiderling logic (summon spiders)
            self.w_cooldown = self.W_COOLDOWN
        else:
            print(f"W on cooldown: {self.w_cooldown} frames")

    def cast_e(self):
        """Cocoon/Rappel - E ability"""
        if self.e_cooldown <= 0:
            self.mana -= 50
            print("Cocoon! (Elise E)")
            # TODO: Implement Cocoon logic (stun/displacement)
            self.e_cooldown = self.E_COOLDOWN
        else:
            print(f"E on cooldown: {self.e_cooldown} frames")


# Alias for backwards compatibility
Player = Amumu

class Blue:

    def __init__(self,world_width, world_height, size=131, speed=2.75):
        self.size = size
        self.radius = size // 2  # Gameplay radius (hitbox for abilities/visuals)
        self.pathing_radius = 30  # Pathing radius (movement collision, smaller than gameplay)
        self.world_width = world_width
        self.world_height = world_height
        self.speed = speed
        self.x = 2627
        self.y = 4794
        
        # Blue Sentinel stats
        self.hp = 2300
        self.max_hp = 2300
        
        # Wall pass-through tag system
        self.can_pass_walls = False  # By default, units cannot pass walls
        self.wall_pass_tags = set()  # Set of tags that allow wall passing
        
        # Movement
        self.target_x = None
        self.target_y = None
        self.is_moving = False
        
        # Aggro / chase / attack system
        self.aggro = False
        self.aggro_target = None  # Reference to the champion being chased
        self.attack_range = 150  # Edge-to-edge attack range
        self.attack_speed = 0.493  # Attacks per second
        self.attack_damage = 66  # Damage per auto-attack
        self.attack_timer = 0.0  # Time remaining in current attack animation
        self.is_attacking = False  # True while in attack animation (cannot move)
        self.attack_damage_dealt = False  # Whether damage has been dealt this attack
        self.ATTACK_WINDUP_PERCENT = 0.321  # 32.1% of attack time is windup
        self.attack_winding_up = False  # True during windup phase (locked in place)
        self.attack_windup_elapsed = 0.0  # Time elapsed in current windup
        self.attack_cooldown = 0.0  # Time remaining before Blue can start a new attack
        self.attack_cooldown_total = 0.0  # Total cooldown duration for bar rendering
  
        self.images = pygame.transform.scale(pygame.image.load("images/blueC.png"), (self.size, self.size))
    
    def add_wall_pass_tag(self, tag):
        """Add a tag that allows this unit to pass through walls"""
        self.wall_pass_tags.add(tag)
    
    def remove_wall_pass_tag(self, tag):
        """Remove a wall pass tag"""
        self.wall_pass_tags.discard(tag)
    
    def has_wall_pass_tag(self, tag):
        """Check if this unit has a specific wall pass tag"""
        return tag in self.wall_pass_tags
    
    def can_pass_wall(self):
        """Check if this unit can currently pass through walls"""
        return len(self.wall_pass_tags) > 0
    
    def set_target(self, target_x, target_y):
        """Set movement target position"""
        self.target_x = target_x
        self.target_y = target_y
        self.is_moving = True
    
    def is_in_attack_range(self, target):
        """Check if target is within attack range (edge-to-edge)."""
        dx = self.x - target.x
        dy = self.y - target.y
        center_distance = math.sqrt(dx**2 + dy**2)
        edge_distance = center_distance - self.radius - target.radius
        return edge_distance <= self.attack_range

    def trigger_aggro(self, target):
        """Called when the champion attacks Blue. Blue starts chasing."""
        if not self.aggro:
            self.aggro = True
            self.aggro_target = target

    def update_ai(self, dt):
        """Update Blue's chase and attack behavior.
        
        Attack phases:
        1. Windup (0% to 32.1%): Locked in place, no damage yet.
        2. Post-windup cooldown (32.1% to 100%): Damage dealt at threshold,
           Blue can move/chase, but cannot start a new attack until the
           full attack duration has elapsed.
        
        Returns:
            Damage dealt to the aggro target this frame (0 if none).
        """
        if not self.aggro or self.aggro_target is None:
            return 0
        
        total_attack_time = 1.0 / self.attack_speed
        windup_time = total_attack_time * self.ATTACK_WINDUP_PERCENT
        damage = 0
        
        # Tick down attack cooldown (post-windup remainder)
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
            if self.attack_cooldown < 0:
                self.attack_cooldown = 0.0
        
        # If currently in windup phase — locked in place
        if self.is_attacking and self.attack_winding_up:
            self.attack_windup_elapsed += dt
            if self.attack_windup_elapsed >= windup_time:
                # Windup complete — deal damage NOW
                damage = self.attack_damage
                self.attack_damage_dealt = True
                self.attack_winding_up = False
                self.is_attacking = False
                # Set cooldown for the remaining attack duration
                remaining = total_attack_time - windup_time
                self.attack_cooldown = remaining
                self.attack_cooldown_total = remaining
                self.attack_windup_elapsed = 0.0
            return damage
        
        # Not in windup — can move, but respect attack cooldown
        if self.is_in_attack_range(self.aggro_target):
            if self.attack_cooldown <= 0:
                # Cooldown done, start a new attack
                self._start_attack()
            else:
                # In range but still on cooldown — stop and wait
                self.is_moving = False
                self.target_x = None
                self.target_y = None
        else:
            # Chase the target
            self.target_x = self.aggro_target.x
            self.target_y = self.aggro_target.y
            self.is_moving = True
        
        return damage
    
    def _start_attack(self):
        """Begin a new attack animation (starts in windup phase)."""
        self.is_attacking = True
        self.attack_winding_up = True
        self.attack_windup_elapsed = 0.0
        self.attack_timer = 1.0 / self.attack_speed
        self.attack_damage_dealt = False
        self.is_moving = False
        self.target_x = None
        self.target_y = None
    
    def check_wall_collision(self, wall_polygons, wall_bounds=None):
        """Check if unit circle collides with any wall polygons.
        Returns True if collision detected and unit cannot pass walls.
        Returns False if unit has wall pass tags or no collision occurs.
        """
        # If unit can pass walls, don't check collision
        if self.can_pass_wall():
            return False
        
        for i, polygon in enumerate(wall_polygons):
            # Fast bounding-box pre-filter
            if wall_bounds and i < len(wall_bounds) and wall_bounds[i]:
                min_x, max_x, min_y, max_y = wall_bounds[i]
                if (self.x + self.radius < min_x or self.x - self.radius > max_x or
                        self.y + self.radius < min_y or self.y - self.radius > max_y):
                    continue
            
            # Check if circle center is inside the polygon
            if point_in_polygon(self.x, self.y, polygon):
                return True
            
            # Check distance from circle center to each polygon edge (use pathing_radius for walls)
            n = len(polygon)
            for j in range(n):
                x1, y1 = polygon[j]
                x2, y2 = polygon[(j + 1) % n]
                if point_to_segment_distance(self.x, self.y, x1, y1, x2, y2) < self.pathing_radius:
                    return True
        
        return False
    
    def check_collision(self, other):
        """Check pathing collision with another unit.
        Uses pathing_radius: a unit's center cannot enter another unit's pathing radius.
        This allows units to partially overlap visually while still blocking movement.
        """
        dx = self.x - other.x
        dy = self.y - other.y
        distance = math.sqrt(dx**2 + dy**2)
        return distance < (self.pathing_radius + other.pathing_radius)
    
    def update_movement(self, collide_with=None, walls=None, wall_polygons=None, wall_bounds=None):
        """Update unit position towards target
        
        Args:
            collide_with: Another unit to check collision with
            walls: (Deprecated) List of wall bounding-box rectangles
            wall_polygons: List of polygon coordinate lists for accurate collision
            wall_bounds: List of (min_x, max_x, min_y, max_y) tuples for fast culling
        """
        if not self.is_moving or self.target_x is None or self.target_y is None:
            return
        
        # Calculate distance to target
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)
        
        # Check if reached target
        if distance < self.speed:
            self.x = self.target_x
            self.y = self.target_y
            self.is_moving = False
            self.target_x = None
            self.target_y = None
            return
        
        # Normalize direction and move
        if distance > 0:
            move_x = (dx / distance) * self.speed
            move_y = (dy / distance) * self.speed
            
            # Store old position in case we need to revert
            old_x = self.x
            old_y = self.y
            
            # Update position (x, y is center of circle)
            self.x += move_x
            self.y += move_y
            
            # Check collisions
            collision_detected = False
            
            # Check unit collision
            if collide_with and self.check_collision(collide_with):
                collision_detected = True
            
            # Check wall collision (unless unit can pass walls)
            if wall_polygons and self.check_wall_collision(wall_polygons, wall_bounds):
                collision_detected = True
            
            # Revert if collision detected
            if collision_detected:
                self.x = old_x
                self.y = old_y
    
    def move():
        pass
        #TODO
    
    def draw(self, screen, camera_x, camera_y):
        # Draw circle at center position
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y
        
        # Draw image centered on position
        if self.images:
            screen.blit(self.images, (int(screen_x - self.radius), int(screen_y - self.radius)))
        else:
            # Draw a simple circle if no image
            pygame.draw.circle(screen, (0, 0, 255), (int(screen_x), int(screen_y)), int(self.radius))
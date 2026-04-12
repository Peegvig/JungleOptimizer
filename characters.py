import random
import pygame
import math
from util import *

class Champion:
    """Base class for all playable champions"""

    def __init__(self, world_width, world_height):
        self.size = 86
        self.x = 3336
        self.y = 7361
        
        self.world_width = world_width
        self.world_height = world_height
        
        # Base stats - override in subclasses
        self.speed = 7.81
        self.hp = 500
        self.max_hp = 500
        self.mana = 300
        self.max_mana = 300
        self.attack_damage = 55
        self.armor = 20
        
        self.score = 0

        # Jungle pet (set by subclass if applicable)
        self.pet = None

        # Circle-based positioning (x, y is now the CENTER of the circle)
        self.radius = 55  # Gameplay radius (hitbox for abilities/autos)
        self.pathing_radius = 30  # Pathing radius (movement collision, smaller than gameplay)
        
        # Movement
        self.target_x = None
        self.target_y = None
        self.is_moving = False
        
        # Pathfinding (A*)
        self._wall_polygons = None
        self._wall_bounds = None
        self._pathfinder = None
        self.path_waypoints = []
        self._path_goal = None
        
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
        self.attack_range = 195  # Edge-to-edge attack range
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
        self._path_goal = None  # Force path recomputation for new target
        
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

    def set_walls(self, wall_polygons, wall_bounds):
        """Provide wall data so champion can build a pathfinding grid."""
        self._wall_polygons = wall_polygons
        self._wall_bounds = wall_bounds
        self._pathfinder = None  # Force rebuild

    def _get_pathfinder(self):
        """Lazy-init the A* grid (built once, reused)."""
        if self._pathfinder is None and self._wall_polygons is not None:
            from util import PathGrid
            self._pathfinder = PathGrid(
                self.world_width, self.world_height,
                self._wall_polygons, self._wall_bounds,
                self.pathing_radius, cell_size=100
            )
        return self._pathfinder

    def _navigate_to(self, goal_x, goal_y):
        """Compute (or reuse) an A* path to the goal and store waypoints."""
        pf = self._get_pathfinder()
        if pf is None:
            # No pathfinder available — fall back to direct movement
            self.path_waypoints = [(goal_x, goal_y)]
            self._path_goal = (goal_x, goal_y)
            return
        # Recompute only if the goal moved significantly
        if self._path_goal is not None:
            dg = math.sqrt((goal_x - self._path_goal[0])**2 + (goal_y - self._path_goal[1])**2)
            if dg < 30 and self.path_waypoints:
                return  # Goal hasn't moved much, keep current path
        self.path_waypoints = pf.find_path(self.x, self.y, goal_x, goal_y)
        self._path_goal = (goal_x, goal_y)

    def _is_position_blocked(self, x, y, collide_with, wall_polygons, wall_bounds):
        """Test if a position is blocked by walls or another unit."""
        old_x, old_y = self.x, self.y
        self.x, self.y = x, y
        blocked = False
        if collide_with and self.check_collision(collide_with):
            blocked = True
        if not blocked and wall_polygons and self.check_wall_collision(wall_polygons, wall_bounds):
            blocked = True
        self.x, self.y = old_x, old_y
        return blocked

    def update_movement(self, collide_with=None, walls=None, wall_polygons=None, wall_bounds=None, can_pass_walls=False):
        """Follow A* waypoints toward the target, like Blue's pathfinding."""
        if not self.is_moving or self.target_x is None or self.target_y is None:
            return
        
        # If we have an attack target and are already in range, stop moving immediately
        if self.attack_target and self.is_in_attack_range(self.attack_target):
            self.is_moving = False
            self.target_x = None
            self.target_y = None
            return

        # Compute / update A* path toward current target
        self._navigate_to(self.target_x, self.target_y)

        if not self.path_waypoints:
            return

        # Step through waypoints
        remaining_speed = self.speed
        while remaining_speed > 0 and self.path_waypoints:
            wp_x, wp_y = self.path_waypoints[0]
            dx = wp_x - self.x
            dy = wp_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < remaining_speed:
                # Reach this waypoint, advance to next
                if not self._is_position_blocked(wp_x, wp_y, collide_with, wall_polygons, wall_bounds):
                    self.x = wp_x
                    self.y = wp_y
                remaining_speed -= dist
                self.path_waypoints.pop(0)
            else:
                # Move toward current waypoint
                dir_x = dx / dist
                dir_y = dy / dist
                new_x = self.x + dir_x * remaining_speed
                new_y = self.y + dir_y * remaining_speed
                if not self._is_position_blocked(new_x, new_y, collide_with, wall_polygons, wall_bounds):
                    self.x = new_x
                    self.y = new_y
                else:
                    # Direct step blocked — try alternate angles
                    base_angle = math.atan2(dir_y, dir_x)
                    moved = False
                    for offset_deg in range(15, 91, 15):
                        for sign in (1, -1):
                            angle = base_angle + math.radians(offset_deg * sign)
                            tx = self.x + math.cos(angle) * remaining_speed
                            ty = self.y + math.sin(angle) * remaining_speed
                            if not self._is_position_blocked(tx, ty, collide_with, wall_polygons, wall_bounds):
                                self.x = tx
                                self.y = ty
                                moved = True
                                break
                        if moved:
                            break
                remaining_speed = 0

        # Check if we've reached the final target
        if not self.path_waypoints:
            dist_to_target = math.sqrt((self.target_x - self.x)**2 + (self.target_y - self.y)**2)
            if dist_to_target < self.speed:
                self.x = self.target_x
                self.y = self.target_y
                self.is_moving = False
                self.target_x = None
                self.target_y = None
                self._path_goal = None
            else:
                # Path consumed but not at target — force recomputation next frame
                self._path_goal = None

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
            # Fast bounding-box pre-filter (use pathing_radius, not gameplay radius)
            if wall_bounds and i < len(wall_bounds) and wall_bounds[i]:
                min_x, max_x, min_y, max_y = wall_bounds[i]
                if (self.x + self.pathing_radius < min_x or self.x - self.pathing_radius > max_x or
                        self.y + self.pathing_radius < min_y or self.y - self.pathing_radius > max_y):
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

    def get_bonus_ad(self):
        return max(0, self.base_attack_damage_value - getattr(self, 'base_ad', self.base_attack_damage_value))

    def get_ap(self):
        return getattr(self, 'ap', 0)

    def get_bonus_armor(self):
        return max(0, self.armor - getattr(self, 'base_armor_value', self.armor))

    def get_bonus_mr(self):
        return max(0, getattr(self, 'magic_resistance', 0) - getattr(self, 'base_mr', 0))

    def get_bonus_health(self):
        return max(0, self.max_hp - getattr(self, 'base_max_hp', self.max_hp))


class Amumu(Champion):
    """The Sad Mummy - Tank jungler"""

    def __init__(self, world_width, world_height):
        super().__init__(world_width, world_height)
        
        # Amumu stats
        self.speed = 5.23
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
        self.attack_range = 195  # Edge-to-edge
        self.attack_speed = 0.736  # Attacks per second
        self.base_attack_damage_value = 57  # Damage per auto-attack
        
        # Load Amumu image
        self.images = pygame.transform.scale(
            pygame.image.load("images/amumuC.png"), 
            (self.size, self.size)
        )

        # Level and bonus stat tracking for pet calculations
        self.level = 1
        self.ap = 0
        self.magic_resistance = 32  # Amumu base MR at level 1
        self.base_ad = self.base_attack_damage_value  # 57
        self.base_armor_value = self.armor  # 25
        self.base_mr = self.magic_resistance  # 32
        self.base_max_hp = self.max_hp  # 510

        # Jungle pet
        self.pet = JunglePet(self)

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
        self.speed = 9.38
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
        self.speed = 7.81
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


class JunglePet:
    """Jungle companion pet that buffs damage dealt/received and attacks monsters."""

    def __init__(self, owner):
        self.owner = owner
        self.attack_radius = 650
        self.tick_interval = 0.5  # Half-second intervals
        self.tick_timer = 0.0
        self.active = False
        self.extra_ticks_remaining = 0  # Ticks remaining after owner stops attacking

        # Damage modifiers for jungle monsters
        self.damage_dealt_modifier = 1.10   # 110% damage to monsters
        self.damage_received_modifier = 0.50  # 50% damage from monsters

    def get_pet_damage_per_second(self, level, is_epic=False):
        """Calculate pet damage per second based on owner level and stats."""
        base = 20 + (70 / 17) * (level - 1)
        bonus_ad = self.owner.get_bonus_ad()
        ap = self.owner.get_ap()
        bonus_armor = self.owner.get_bonus_armor()
        bonus_mr = self.owner.get_bonus_mr()
        bonus_health = self.owner.get_bonus_health()
        scaling = (0.10 * bonus_ad + 0.12 * ap +
                   0.20 * bonus_armor + 0.20 * bonus_mr +
                   0.03 * bonus_health)
        if is_epic:
            base = min(base, 15.5)
        return base + scaling

    def get_damage_breakdown(self, level, is_epic=False):
        """Return detailed breakdown of pet damage components."""
        base = 20 + (70 / 17) * (level - 1)
        bonus_ad = self.owner.get_bonus_ad()
        ap = self.owner.get_ap()
        bonus_armor = self.owner.get_bonus_armor()
        bonus_mr = self.owner.get_bonus_mr()
        bonus_health = self.owner.get_bonus_health()
        ad_c = 0.10 * bonus_ad
        ap_c = 0.12 * ap
        armor_c = 0.20 * bonus_armor
        mr_c = 0.20 * bonus_mr
        hp_c = 0.03 * bonus_health
        if is_epic:
            base = min(base, 15.5)
        return {
            'total': base + ad_c + ap_c + armor_c + mr_c + hp_c,
            'base': base, 'ad': ad_c, 'ap': ap_c,
            'armor': armor_c, 'mr': mr_c, 'hp': hp_c,
        }

    def get_heal_per_second(self, level):
        """Calculate heal per second based on owner level."""
        return 14 + 2 * (level - 1)

    def update(self, dt, monsters_attacking_owner):
        """Tick the pet. Returns (damage_dict {monster: dmg}, heal_amount, tick_fired)."""
        damage_dict = {}
        heal = 0.0
        tick_fired = False

        owner_attacking = self.owner.attack_target is not None

        if owner_attacking:
            self.active = True
            self.extra_ticks_remaining = 4  # 2 full attacks = 4 half-second ticks

        if not self.active:
            return damage_dict, heal, tick_fired

        # Gather valid targets within attack radius
        targets = []
        for m in monsters_attacking_owner:
            dx = m.x - self.owner.x
            dy = m.y - self.owner.y
            if math.sqrt(dx**2 + dy**2) <= self.attack_radius:
                targets.append(m)

        if not targets and not owner_attacking:
            self.active = False
            self.tick_timer = 0.0
            return damage_dict, heal, tick_fired

        self.tick_timer += dt
        while self.tick_timer >= self.tick_interval and self.active:
            self.tick_timer -= self.tick_interval
            tick_fired = True
            level = self.owner.level

            for m in targets:
                is_epic = getattr(m, 'is_epic', False)
                per_sec = self.get_pet_damage_per_second(level, is_epic)
                tick_dmg = per_sec / 2  # Half-second tick = half per-second damage
                if m not in damage_dict:
                    damage_dict[m] = 0
                damage_dict[m] += tick_dmg

            heal_per_sec = self.get_heal_per_second(level)
            heal += heal_per_sec / 2

            if not owner_attacking:
                self.extra_ticks_remaining -= 1
                if self.extra_ticks_remaining <= 0:
                    self.active = False
                    break

        return damage_dict, heal, tick_fired


class Blue:

    def __init__(self,world_width, world_height, size=205, speed=4.22):
        self.size = size
        self.radius = 131  # Gameplay radius (hitbox for abilities/visuals)
        self.pathing_radius = 30  # Pathing radius (movement collision, smaller than gameplay)
        self.world_width = world_width
        self.world_height = world_height
        self.speed = speed
        self.x = 4105
        self.y = 7491

        # Monster type flags
        self.is_jungle_monster = True
        self.is_epic = False  # Not an epic monster (Dragon/Baron/Herald)
        
        # Blue Sentinel stats
        self.hp = 2300
        self.max_hp = 2300
        
        # Pathfinding
        self._wall_polygons = None
        self._wall_bounds = None
        self._pathfinder = None  # Lazy-init PathGrid
        self.path_waypoints = []  # List of (x, y) waypoints to follow
        self._path_goal = None   # Current goal the path was computed for
        
        # Movement
        self.target_x = None
        self.target_y = None
        self.is_moving = False
        
        # Aggro / chase / attack system
        self.aggro = False
        self.aggro_target = None  # Reference to the champion being chased
        self.attack_range = 234  # Edge-to-edge attack range
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
        
        # Remember spawn position
        self.spawn_x = self.x
        self.spawn_y = self.y
        
        # Patience system
        self.patience = 100.0
        self.patience_max = 100.0
        self.leash_range = 650  # Distance from spawn before patience drains
        
        # Reset state machine
        self.RESET_NONE = 0
        self.RESET_SOFT = 1
        self.RESET_HARD = 2
        self.reset_state = self.RESET_NONE
        self.soft_reset_timer = 0.0
        self.SOFT_RESET_DURATION = 6.0  # Seconds before soft reset becomes hard reset
        
        # Speed variants (scaled for 16000 world)
        self.base_speed = speed  # Normal chase speed (270 MS)
        self.soft_reset_speed = 5.16  # Walk back during soft reset (330 MS)
        self.hard_reset_speed = 5.16  # Run back during hard reset (330 MS)
        
        # Healing rates during reset (fraction of max HP per second)
        self.SOFT_HEAL_PERCENT = 0.06  # 6% max HP per second
        self.HARD_HEAL_PERCENT = 0.25  # 25% max HP per second (rapid)
        
        # Patience immunity (after attack cancels soft reset)
        self.patience_immunity_timer = 0.0
        self.PATIENCE_IMMUNITY_DURATION = 1.5  # Seconds of patience loss immunity
        
        # Patience recovery at spawn (after hard reset)
        self.at_spawn_timer = 0.0
        self.patience_recovering = False
        self.PATIENCE_RECOVERY_DELAY = 2.0  # Wait 2s before recovering patience
        self.PATIENCE_RECOVERY_DURATION = 2.0  # Recover patience over 2s
        
        # Leash range circle visibility
        self.leash_circle_visible = False
        self.leash_circle_timer = 0.0
        self.LEASH_CIRCLE_DURATION = 3.0  # Visible for 3s after last attack
    
    def set_walls(self, wall_polygons, wall_bounds):
        """Provide wall data so Blue can build a pathfinding grid."""
        self._wall_polygons = wall_polygons
        self._wall_bounds = wall_bounds
        self._pathfinder = None  # Force rebuild

    def _get_pathfinder(self):
        """Lazy-init the A* grid (built once, reused)."""
        if self._pathfinder is None and self._wall_polygons is not None:
            from util import PathGrid
            self._pathfinder = PathGrid(
                self.world_width, self.world_height,
                self._wall_polygons, self._wall_bounds,
                self.pathing_radius, cell_size=100
            )
        return self._pathfinder

    def _navigate_to(self, goal_x, goal_y):
        """Compute (or reuse) an A* path to the goal and store waypoints."""
        pf = self._get_pathfinder()
        if pf is None:
            # No pathfinder available — fall back to direct movement
            self.path_waypoints = [(goal_x, goal_y)]
            self._path_goal = (goal_x, goal_y)
            return
        # Recompute only if the goal moved significantly
        if self._path_goal is not None:
            dg = math.sqrt((goal_x - self._path_goal[0])**2 + (goal_y - self._path_goal[1])**2)
            if dg < 30 and self.path_waypoints:
                return  # Goal hasn't moved much, keep current path
        self.path_waypoints = pf.find_path(self.x, self.y, goal_x, goal_y)
        self._path_goal = (goal_x, goal_y)

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
        """Called when the champion attacks/damages Blue. Handles patience interactions."""
        # Hard reset: completely ignore all aggression
        if self.reset_state == self.RESET_HARD:
            return
        
        # Soft reset: only respond if within leash range (cancel reset)
        if self.reset_state == self.RESET_SOFT:
            if self.distance_from_spawn() <= self.leash_range:
                self.cancel_soft_reset(target)
            return
        
        # Normal aggro
        if not self.aggro:
            self.aggro = True
            self.aggro_target = target
            self.patience = self.patience_max
        
        # Refresh leash circle visibility
        self.leash_circle_visible = True
        self.leash_circle_timer = self.LEASH_CIRCLE_DURATION

    def update_ai(self, dt):
        """Update Blue's AI: patience, reset, chase, and attack behavior.
        
        Returns:
            Damage dealt to the aggro target this frame (0 if none).
        """
        # Update leash circle timer
        if self.leash_circle_visible:
            self.leash_circle_timer -= dt
            if self.leash_circle_timer <= 0:
                self.leash_circle_visible = False
        
        # Handle reset states (soft or hard reset)
        if self.reset_state != self.RESET_NONE:
            return self._update_reset(dt)
        
        # Handle patience recovery at spawn
        if self.patience_recovering:
            self._update_patience_recovery(dt)
            return 0
        
        if not self.aggro or self.aggro_target is None:
            return 0
        
        # Update patience immunity timer
        if self.patience_immunity_timer > 0:
            self.patience_immunity_timer -= dt
        
        # Deplete patience when outside leash range
        # (but not if the aggro target is still within leash range)
        dist = self.distance_from_spawn()
        target_in_range = False
        if self.aggro_target is not None:
            tdx = self.aggro_target.x - self.spawn_x
            tdy = self.aggro_target.y - self.spawn_y
            target_in_range = math.sqrt(tdx**2 + tdy**2) <= self.leash_range
        if dist > self.leash_range and self.patience_immunity_timer <= 0 and not target_in_range:
            excess = dist - self.leash_range
            depletion_rate = 8.0 + excess * 0.08
            self.patience -= depletion_rate * dt
            if self.patience <= 0:
                self.patience = 0
                self._start_soft_reset()
                return 0
        
        # Normal attack logic
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
    
    def distance_from_spawn(self):
        """Get current distance from spawn point."""
        dx = self.x - self.spawn_x
        dy = self.y - self.spawn_y
        return math.sqrt(dx**2 + dy**2)
    
    def _start_soft_reset(self):
        """Enter soft reset state. Blue slowly walks back, heals, ignores attackers outside leash."""
        self.reset_state = self.RESET_SOFT
        self.soft_reset_timer = 0.0
        self.speed = self.soft_reset_speed
        # Cancel any ongoing attack
        self.is_attacking = False
        self.attack_winding_up = False
        self.attack_windup_elapsed = 0.0
        self.attack_cooldown = 0.0
        # Walk to spawn
        self.target_x = self.spawn_x
        self.target_y = self.spawn_y
        self.is_moving = True
    
    def _start_hard_reset(self):
        """Transition from soft to hard reset. Ignores all attackers, runs back fast."""
        self.reset_state = self.RESET_HARD
        self.speed = self.hard_reset_speed
        self.target_x = self.spawn_x
        self.target_y = self.spawn_y
        self.is_moving = True
    
    def cancel_soft_reset(self, target):
        """Cancel soft reset when attacked within leash range. Restores some patience."""
        self.reset_state = self.RESET_NONE
        self.soft_reset_timer = 0.0
        self.speed = self.base_speed
        self.aggro = True
        self.aggro_target = target
        self.patience = min(self.patience_max, self.patience + 30.0)
        self.patience_immunity_timer = self.PATIENCE_IMMUNITY_DURATION
    
    def _update_reset(self, dt):
        """Update Blue during soft or hard reset. Returns 0 (no damage during reset)."""
        # Heal based on reset type
        if self.reset_state == self.RESET_SOFT:
            self.hp = min(self.max_hp, self.hp + self.max_hp * self.SOFT_HEAL_PERCENT * dt)
            self.soft_reset_timer += dt
            # After 6 seconds, transition to hard reset
            if self.soft_reset_timer >= self.SOFT_RESET_DURATION:
                self._start_hard_reset()
        elif self.reset_state == self.RESET_HARD:
            self.hp = min(self.max_hp, self.hp + self.max_hp * self.HARD_HEAL_PERCENT * dt)
        
        # Keep walking toward spawn
        self.target_x = self.spawn_x
        self.target_y = self.spawn_y
        self.is_moving = True
        
        # Check if reached spawn
        dist = self.distance_from_spawn()
        if dist < self.speed:
            self.x = self.spawn_x
            self.y = self.spawn_y
            self._arrive_at_spawn()
        
        return 0
    
    def _arrive_at_spawn(self):
        """Called when Blue arrives back at spawn after resetting."""
        self.reset_state = self.RESET_NONE
        self.speed = self.base_speed
        self.hp = self.max_hp  # Full heal
        self.aggro = False
        self.aggro_target = None
        self.is_moving = False
        self.target_x = None
        self.target_y = None
        self.is_attacking = False
        self.attack_winding_up = False
        self.attack_windup_elapsed = 0.0
        self.attack_cooldown = 0.0
        self.patience_recovering = True
        self.at_spawn_timer = 0.0
        self.leash_circle_visible = False
    
    def _update_patience_recovery(self, dt):
        """Recover patience after arriving at spawn. 2s delay then 2s fill."""
        self.at_spawn_timer += dt
        if self.at_spawn_timer < self.PATIENCE_RECOVERY_DELAY:
            return  # Still waiting
        recovery_elapsed = self.at_spawn_timer - self.PATIENCE_RECOVERY_DELAY
        self.patience = min(
            self.patience_max,
            (recovery_elapsed / self.PATIENCE_RECOVERY_DURATION) * self.patience_max
        )
        if self.patience >= self.patience_max:
            self.patience = self.patience_max
            self.patience_recovering = False
    
    def check_wall_collision(self, wall_polygons, wall_bounds=None):
        """Check if unit circle collides with any wall polygons."""
        for i, polygon in enumerate(wall_polygons):
            # Fast bounding-box pre-filter (use pathing_radius, not gameplay radius)
            if wall_bounds and i < len(wall_bounds) and wall_bounds[i]:
                min_x, max_x, min_y, max_y = wall_bounds[i]
                if (self.x + self.pathing_radius < min_x or self.x - self.pathing_radius > max_x or
                        self.y + self.pathing_radius < min_y or self.y - self.pathing_radius > max_y):
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
    
    def _is_position_blocked(self, x, y, collide_with, wall_polygons, wall_bounds):
        """Test if a position is blocked by walls or another unit."""
        old_x, old_y = self.x, self.y
        self.x, self.y = x, y
        blocked = False
        if collide_with and self.check_collision(collide_with):
            blocked = True
        if not blocked and wall_polygons and self.check_wall_collision(wall_polygons, wall_bounds):
            blocked = True
        self.x, self.y = old_x, old_y
        return blocked

    def update_movement(self, collide_with=None, walls=None, wall_polygons=None, wall_bounds=None):
        """Follow A* waypoints toward the target. Recomputes path when chasing a moving target."""
        if not self.is_moving or self.target_x is None or self.target_y is None:
            return

        # Compute / update A* path toward current target
        self._navigate_to(self.target_x, self.target_y)

        if not self.path_waypoints:
            return

        # Step through waypoints
        remaining_speed = self.speed
        while remaining_speed > 0 and self.path_waypoints:
            wp_x, wp_y = self.path_waypoints[0]
            dx = wp_x - self.x
            dy = wp_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < remaining_speed:
                # Reach this waypoint, advance to next
                if not self._is_position_blocked(wp_x, wp_y, collide_with, wall_polygons, wall_bounds):
                    self.x = wp_x
                    self.y = wp_y
                remaining_speed -= dist
                self.path_waypoints.pop(0)
            else:
                # Move toward current waypoint
                dir_x = dx / dist
                dir_y = dy / dist
                new_x = self.x + dir_x * remaining_speed
                new_y = self.y + dir_y * remaining_speed
                if not self._is_position_blocked(new_x, new_y, collide_with, wall_polygons, wall_bounds):
                    self.x = new_x
                    self.y = new_y
                else:
                    # Direct step blocked by fine-grained wall — try alternate angles
                    base_angle = math.atan2(dir_y, dir_x)
                    moved = False
                    for offset_deg in range(15, 91, 15):
                        for sign in (1, -1):
                            angle = base_angle + math.radians(offset_deg * sign)
                            tx = self.x + math.cos(angle) * remaining_speed
                            ty = self.y + math.sin(angle) * remaining_speed
                            if not self._is_position_blocked(tx, ty, collide_with, wall_polygons, wall_bounds):
                                self.x = tx
                                self.y = ty
                                moved = True
                                break
                        if moved:
                            break
                remaining_speed = 0

        # Check if we've reached the final target
        if not self.path_waypoints:
            dist_to_target = math.sqrt((self.target_x - self.x)**2 + (self.target_y - self.y)**2)
            if dist_to_target < self.speed:
                self.x = self.target_x
                self.y = self.target_y
                self.is_moving = False
                self.target_x = None
                self.target_y = None
                self._path_goal = None
            else:
                # Path consumed but not at target — force recomputation next frame
                self._path_goal = None
    
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
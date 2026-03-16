#!/usr/bin/env python3
"""Test script to verify wall loading from JSON"""

import json
import pygame

# Test loading walls
try:
    with open("walls.json", "r") as f:
        walls_data = json.load(f)
    
    print(f"✓ Successfully loaded walls.json")
    print(f"✓ Number of polygons: {len(walls_data)}")
    
    if isinstance(walls_data, list) and len(walls_data) > 0:
        first_wall = walls_data[0]
        print(f"✓ First wall has {len(first_wall)} coordinate points")
        print(f"  Sample point: {first_wall[0]}")
        
        # Test the wall parsing logic (same as in game.py)
        walls = []
        for polygon_coords in walls_data:
            if isinstance(polygon_coords, list) and len(polygon_coords) > 0:
                xs = []
                ys = []
                for coord in polygon_coords:
                    if isinstance(coord, (list, tuple)) and len(coord) == 2:
                        xs.append(coord[0])
                        ys.append(coord[1])
                
                if xs and ys:
                    min_x = min(xs)
                    max_x = max(xs)
                    min_y = min(ys)
                    max_y = max(ys)
                    
                    width = max_x - min_x
                    height = max_y - min_y
                    
                    if width > 0 and height > 0:
                        walls.append((min_x, min_y, width, height))
        
        print(f"✓ Successfully parsed {len(walls)} wall rectangles")
        print(f"  First wall rect: x={walls[0][0]:.1f}, y={walls[0][1]:.1f}, w={walls[0][2]:.1f}, h={walls[0][3]:.1f}")
        
except FileNotFoundError:
    print("✗ walls.json not found!")
except json.JSONDecodeError as e:
    print(f"✗ Error parsing JSON: {e}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")

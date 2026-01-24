
def check_collision(rect, rect_list):
    for other_rect in rect_list:
        if rect.colliderect(other_rect):
            return True
    return False

def get_collision(rect, rect_list):
    for other_rect in rect_list:
        if rect.colliderect(other_rect):
            return other_rect
    return None


import pygame
import random
import sys

# --- 設定と定数 ---
SCREEN_SIZE = 600
GRID_SIZE = 15
TILE = SCREEN_SIZE // GRID_SIZE
FPS = 60

COLORS = {
    "RED": (255, 50, 50), "GREEN": (50, 255, 50),
    "YELLOW": (255, 255, 50), "BLUE": (50, 50, 255),
    "WHITE": (240, 240, 240), "BLACK": (30, 30, 30),
    "GRAY": (200, 200, 200), "DARK_GRAY": (70, 70, 70),
    "GOLD": (218, 165, 32)
}

BASE_COORDS = [(0, 0), (9, 0), (9, 9), (0, 9)]
START_INDICES = [0, 13, 26, 39]

# --- クラス定義 ---

class Token:
    def __init__(self, color, player_id, token_id):
        self.color = color
        self.player_id = player_id
        self.token_id = token_id
        self.index = -1
        self.display_pos = [0, 0]
        self.reset_to_base()
        self.move_queue = []

    def reset_to_base(self):
        self.index = -1
        bx, by = BASE_COORDS[self.player_id]
        offsets = [(1.5, 1.5), (3.5, 1.5), (1.5, 3.5), (3.5, 3.5)]
        ox, oy = offsets[self.token_id]
        self.display_pos = [(bx + ox) * TILE, (by + oy) * TILE]

    def start_move(self, steps, route_coords):
        for _ in range(steps):
            if self.index < 56:
                self.index += 1
                target_pos = route_coords[self.index]
                self.move_queue.append(target_pos)
            else:
                break

    def update(self):
        if self.move_queue:
            target = self.move_queue[0]
            dx = target[0] - self.display_pos[0]
            dy = target[1] - self.display_pos[1]
            dist = (dx**2 + dy**2)**0.5
            
            if dist < 8:
                self.display_pos = list(target)
                self.move_queue.pop(0)
                return True
            else:
                self.display_pos[0] += (dx / dist) * 10
                self.display_pos[1] += (dy / dist) * 10
        return False

    def get_global_index(self):
        if self.index == -1 or self.index >= 51:
            return -1
        return (START_INDICES[self.player_id] + self.index) % 52


class GameManager:
    def __init__(self, player_configs, difficulty="NORMAL"):
        self.players = player_configs
        self.difficulty = difficulty
        self.turn = 0
        self.dice_value = 1
        self.state = "ROLLING"  # ROLLING, DICE_ANIM, CHOOSING, ANIMATING, GAME_OVER
        self.cpu_timer = 0
        self.has_bonus_turn = False
        self.winner = None
        
        # サイコロアニメーション用の管理変数
        self.dice_anim_timer = 0
        self.dice_anim_view_value = 1  # アニメ中に入れ替わる仮の目
        self.final_dice_target = 1      # 最終的に確定する出目
        
        self.common_route = self.generate_common_route()
        self.player_routes = {i: self.generate_player_route(i) for i in range(len(self.players))}
        self.tokens = [Token(p["color"], i, t) for i, p in enumerate(self.players) for t in range(4)]

    def generate_common_route(self):
        steps = [
            (1,6), (2,6), (3,6), (4,6), (5,6),
            (6,5), (6,4), (6,3), (6,2), (6,1), (6,0),
            (7,0), (8,0),
            (8,1), (8,2), (8,3), (8,4), (8,5),
            (9,6), (10,6), (11,6), (12,6), (13,6), (14,6),
            (14,7), (14,8),
            (13,8), (12,8), (11,8), (10,8), (9,8),
            (8,9), (8,10), (8,11), (8,12), (8,13), (8,14),
            (7,14), (6,14),
            (6,13), (6,12), (6,11), (6,10), (6,9),
            (5,8), (4,8), (3,8), (2,8), (1,8), (0,8),
            (0,7), (0,6)
        ]
        return [(cx * TILE + TILE//2, cy * TILE + TILE//2) for cx, cy in steps]

    def generate_player_route(self, player_id):
        route = []
        start_idx = START_INDICES[player_id]
        for i in range(51):
            route.append(self.common_route[(start_idx + i) % 52])
        home_steps = []
        if player_id == 0:   home_steps = [(i, 7) for i in range(1, 7)]
        elif player_id == 1: home_steps = [(7, i) for i in range(1, 7)]
        elif player_id == 2: home_steps = [(13 - i, 7) for i in range(6)]
        elif player_id == 3: home_steps = [(7, 13 - i) for i in range(6)]
        for cx, cy in home_steps:
            route.append((cx * TILE + TILE//2, cy * TILE + TILE//2))
        return route

    def get_global_occupancy(self):
        occupancy = {}
        for t in self.tokens:
            g_idx = t.get_global_index()
            if g_idx != -1:
                if g_idx not in occupancy:
                    occupancy[g_idx] = {}
                occupancy[g_idx][t.player_id] = occupancy[g_idx].get(t.player_id, 0) + 1
        return occupancy

    def is_block_at_global(self, g_idx, asking_player_id):
        occupancy = self.get_global_occupancy()
        if g_idx in occupancy:
            for p_id, count in occupancy[g_idx].items():
                if p_id != asking_player_id and count >= 2:
                    return True
        return False

    def start_dice_roll_animation(self):
        """【新機能】サイコロの計算を行い、アニメーション状態に移行する"""
        if self.state != "ROLLING": return
        
        # 内部的な確定出目を先に計算
        if self.difficulty == "HARD" and self.players[self.turn]["type"] == "CPU":
            weights = [1, 1, 1, 1, 1, 1]
            has_in_base = any(t.index == -1 for t in self.get_current_tokens())
            if has_in_base:
                weights[5] = 3
            self.final_dice_target = random.choices([1,2,3,4,5,6], weights=weights)[0]
        else:
            self.final_dice_target = random.randint(1, 6)
            
        # アニメーション状態へ
        self.state = "DICE_ANIM"
        self.dice_anim_timer = 0

    def update_dice_animation(self, dt):
        """【新機能】サイコロのパラパラアニメを更新処理するメソッド"""
        if self.state != "DICE_ANIM": return
        
        self.dice_anim_timer += dt
        # 50ミリ秒(0.05秒)ごとに表示される目を高速シャッフル
        if random.randint(1, 3) == 1:
            self.dice_anim_view_value = random.randint(1, 6)
            
        # 350ミリ秒(0.35秒)経過したらアニメ終了、本決定へ
        if self.dice_anim_timer > 350:
            self.dice_value = self.final_dice_target
            self.dice_anim_view_value = self.dice_value
            
            movable_tokens = self.get_movable_tokens()
            if not movable_tokens:
                self.state = "ANIMATING"
            else:
                self.state = "CHOOSING"

    def get_movable_tokens(self):
        movable = []
        for t in self.get_current_tokens():
            if t.index == 56: continue
            if t.index == -1 and self.dice_value != 6: continue
            if t.index + self.dice_value > 56: continue
            
            blocked = False
            current_idx = t.index
            for step in range(1, self.dice_value): 
                test_local_idx = current_idx + step if current_idx != -1 else 0
                if test_local_idx < 51:
                    test_global_idx = (START_INDICES[t.player_id] + test_local_idx) % 52
                    if self.is_block_at_global(test_global_idx, self.turn):
                        blocked = True
                        break
            if not blocked:
                movable.append(t)
        return movable

    def handle_click(self, pos):
        if self.state == "GAME_OVER" or self.state == "DICE_ANIM": return
        
        if self.state == "ROLLING" and self.players[self.turn]["type"] == "HUMAN":
            self.start_dice_roll_animation()
        elif self.state == "CHOOSING" and self.players[self.turn]["type"] == "HUMAN":
            for t in self.get_movable_tokens():
                dist = ((pos[0] - t.display_pos[0])**2 + (pos[1] - t.display_pos[1])**2)**0.5
                if dist < TILE:
                    self.execute_move(t)
                    break

    def execute_move(self, token):
        if token.index == -1 and self.dice_value == 6:
            token.index = 0
            token.display_pos = list(self.player_routes[self.turn][0])
            self.state = "ANIMATING"
        else:
            token.start_move(self.dice_value, self.player_routes[self.turn])
            self.state = "ANIMATING"

    def check_captures(self, moved_token):
        my_global_pos = moved_token.get_global_index()
        if my_global_pos == -1: return

        captured_count = 0
        for t in self.tokens:
            if t.player_id != self.turn and t.get_global_index() == my_global_pos:
                t.reset_to_base()
                captured_count += 1
                self.has_bonus_turn = True

        if captured_count > 0:
            print(f"💥 大逆転！【{moved_token.color}】が【{captured_count}個】の敵コマをまとめて撃破！")

    def check_game_clear(self):
        current_tokens = self.get_current_tokens()
        goal_count = sum(1 for t in current_tokens if t.index == 56)
        if goal_count == 4:
            self.winner = self.players[self.turn]["color"]
            self.state = "GAME_OVER"
            return True
        return False

    def get_current_tokens(self):
        return [t for t in self.tokens if t.player_id == self.turn]

    def next_turn(self):
        if self.state == "GAME_OVER": return
        if self.check_game_clear(): return

        if self.dice_value == 6 or self.has_bonus_turn:
            pass 
        else:
            self.turn = (self.turn + 1) % len(self.players)
            
        self.has_bonus_turn = False
        self.state = "ROLLING"

    def cpu_think(self):
        movable = self.get_movable_tokens()
        if not movable: return None

        if self.difficulty == "EASY":
            return random.choice(movable)

        elif self.difficulty == "NORMAL":
            target_token = movable[0]
            max_kills = 0
            for t in movable:
                next_idx = t.index + self.dice_value
                if next_idx < 51:
                    future_global = (START_INDICES[t.player_id] + next_idx) % 52
                    occupancy = self.get_global_occupancy()
                    if future_global in occupancy:
                        kills = sum(count for p_id, count in occupancy[future_global].items() if p_id != self.turn)
                        if kills > max_kills:
                            max_kills = kills
                            target_token = t
            return target_token

        elif self.difficulty == "HARD":
            best_token = movable[0]
            best_score = -999
            for t in movable:
                score = 0
                next_idx = t.index + self.dice_value
                if next_idx == 56: score += 500
                if next_idx < 51:
                    future_global = (START_INDICES[t.player_id] + next_idx) % 52
                    occupancy = self.get_global_occupancy()
                    if future_global in occupancy:
                        kills = sum(count for p_id, count in occupancy[future_global].items() if p_id != self.turn)
                        score += kills * 100
                    if future_global in occupancy and self.turn in occupancy[future_global]:
                        score += 30 
                score += t.index
                if score > best_score:
                    best_score = score
                    best_token = t
            return best_token


# --- 盤面描画関数 ---
def draw_board(screen):
    screen.fill(COLORS["WHITE"])
    pygame.draw.rect(screen, COLORS["RED"], (0, 0, TILE*6, TILE*6))
    pygame.draw.rect(screen, COLORS["GREEN"], (TILE*9, 0, TILE*6, TILE*6))
    pygame.draw.rect(screen, COLORS["YELLOW"], (TILE*9, TILE*9, TILE*6, TILE*6))
    pygame.draw.rect(screen, COLORS["BLUE"], (0, TILE*9, TILE*6, TILE*6))
    
    pygame.draw.rect(screen, COLORS["WHITE"], (TILE, TILE, TILE*4, TILE*4))
    pygame.draw.rect(screen, COLORS["WHITE"], (TILE*10, TILE, TILE*4, TILE*4))
    pygame.draw.rect(screen, COLORS["WHITE"], (TILE*10, TILE*10, TILE*4, TILE*4))
    pygame.draw.rect(screen, COLORS["WHITE"], (TILE, TILE*10, TILE*4, TILE*4))

    center_points = [(TILE*6, TILE*6), (TILE*9, TILE*6), (TILE*9, TILE*9), (TILE*6, TILE*9), (TILE*7.5, TILE*7.5)]
    pygame.draw.polygon(screen, COLORS["RED"], [center_points[0], center_points[3], center_points[4]])
    pygame.draw.polygon(screen, COLORS["GREEN"], [center_points[0], center_points[1], center_points[4]])
    pygame.draw.polygon(screen, COLORS["YELLOW"], [center_points[1], center_points[2], center_points[4]])
    pygame.draw.polygon(screen, COLORS["BLUE"], [center_points[2], center_points[3], center_points[4]])

    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if (6 <= x <= 8) or (6 <= y <= 8):
                rect = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                pygame.draw.rect(screen, COLORS["GRAY"], rect, 1)
                
                if x == 7 and 1 <= y <= 5: pygame.draw.rect(screen, COLORS["GREEN"], rect)
                if x == 7 and 9 <= y <= 13: pygame.draw.rect(screen, COLORS["BLUE"], rect)
                if y == 7 and 1 <= x <= 5: pygame.draw.rect(screen, COLORS["RED"], rect)
                if y == 7 and 9 <= x <= 13: pygame.draw.rect(screen, COLORS["YELLOW"], rect)
                
                if x == 1 and y == 6: pygame.draw.rect(screen, COLORS["RED"], rect)
                if x == 8 and y == 1: pygame.draw.rect(screen, COLORS["GREEN"], rect)
                if x == 13 and y == 8: pygame.draw.rect(screen, COLORS["YELLOW"], rect)
                if x == 6 and y == 13: pygame.draw.rect(screen, COLORS["BLUE"], rect)

    pygame.draw.rect(screen, COLORS["BLACK"], (0, 0, SCREEN_SIZE, SCREEN_SIZE), 3)


def draw_dice(screen, val, x, y, size=35):
    """【新機能】サイコロの目(ドット)を正確にグラフィックとしてレンダリングする"""
    # サイコロの白い土台
    pygame.draw.rect(screen, COLORS["WHITE"], (x, y, size, size), 0, 5)
    pygame.draw.rect(screen, COLORS["BLACK"], (x, y, size, size), 2, 5)
    
    # ドットの座標比率
    r = size // 6
    cx, cy = x + size // 2, y + size // 2
    dots = []
    
    if val == 1:
        pygame.draw.circle(screen, COLORS["RED"], (cx, cy), r + 1) # 1の目は赤丸
        return
    elif val == 2: dots = [(-r*1.5, -r*1.5), (r*1.5, r*1.5)]
    elif val == 3: dots = [(-r*1.5, -r*1.5), (0, 0), (r*1.5, r*1.5)]
    elif val == 4: dots = [(-r*1.5, -r*1.5), (r*1.5, -r*1.5), (-r*1.5, r*1.5), (r*1.5, r*1.5)]
    elif val == 5: dots = [(-r*1.5, -r*1.5), (r*1.5, -r*1.5), (0, 0), (-r*1.5, r*1.5), (r*1.5, r*1.5)]
    elif val == 6: dots = [(-r*1.5, -r*1.5), (r*1.5, -r*1.5), (-r*1.5, 0), (r*1.5, 0), (-r*1.5, r*1.5), (r*1.5, r*1.5)]

    for dx, dy in dots:
        pygame.draw.circle(screen, COLORS["BLACK"], (int(cx + dx), int(cy + dy)), r - 1)


# --- メイン関数 ---
def main():
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((SCREEN_SIZE, SCREEN_SIZE))
    pygame.display.set_caption("Ludo: Dynamic Dice Animation Edition")
    clock = pygame.time.Clock()
    
    font = pygame.font.SysFont("arial", 24)
    large_font = pygame.font.SysFont("arial", 40, bold=True)
    
    btn_easy = pygame.Rect(200, 220, 200, 50)
    btn_normal = pygame.Rect(200, 300, 200, 50)
    btn_hard = pygame.Rect(200, 380, 200, 50)
    
    selected_difficulty = None
    in_menu = True

    # 1. メニュー画面
    while in_menu:
        screen.fill(COLORS["WHITE"])
        title = large_font.render("SELECT DIFFICULTY", True, COLORS["BLACK"])
        screen.blit(title, (SCREEN_SIZE // 2 - title.get_width() // 2, 100))
        
        pygame.draw.rect(screen, COLORS["GREEN"], btn_easy, 0, 5)
        pygame.draw.rect(screen, COLORS["YELLOW"], btn_normal, 0, 5)
        pygame.draw.rect(screen, COLORS["RED"], btn_hard, 0, 5)
        
        txt_easy = font.render("EASY", True, COLORS["BLACK"])
        txt_normal = font.render("NORMAL", True, COLORS["BLACK"])
        txt_hard = font.render("HARD", True, COLORS["WHITE"])
        
        screen.blit(txt_easy, (btn_easy.centerx - txt_easy.get_width()//2, btn_easy.centery - txt_easy.get_height()//2))
        screen.blit(txt_normal, (btn_normal.centerx - txt_normal.get_width()//2, btn_normal.centery - txt_normal.get_height()//2))
        screen.blit(txt_hard, (btn_hard.centerx - txt_hard.get_width()//2, btn_hard.centery - txt_hard.get_height()//2))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_easy.collidepoint(event.pos): selected_difficulty = "EASY"; in_menu = False
                elif btn_normal.collidepoint(event.pos): selected_difficulty = "NORMAL"; in_menu = False
                elif btn_hard.collidepoint(event.pos): selected_difficulty = "HARD"; in_menu = False
        pygame.display.flip()
        clock.tick(FPS)

    configs = [
        {"type": "HUMAN", "color": "RED"},
        {"type": "CPU", "color": "GREEN"},
        {"type": "CPU", "color": "YELLOW"},
        {"type": "CPU", "color": "BLUE"}
    ]
    gm = GameManager(configs, selected_difficulty)

    # 2. メインゲームループ
    while True:
        dt = clock.get_time() # 前のフレームからの経過時間（ミリ秒）を取得
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                gm.handle_click(event.pos)

        # サイコロアニメの毎フレーム更新
        if gm.state == "DICE_ANIM":
            gm.update_dice_animation(dt)

        # CPU自動思考
        if gm.state != "GAME_OVER" and gm.players[gm.turn]["type"] == "CPU":
            gm.cpu_timer += dt
            if gm.cpu_timer > 400:
                if gm.state == "ROLLING":
                    gm.start_dice_roll_animation()
                elif gm.state == "CHOOSING":
                    target_token = gm.cpu_think()
                    if target_token:
                        gm.execute_move(target_token)
                gm.cpu_timer = 0

        # 移動アニメーション更新
        moving = False
        last_moved_token = None
        for t in gm.tokens:
            if t.update(): pass
            if t.move_queue:
                moving = True
                last_moved_token = t
        
        if gm.state == "ANIMATING" and not moving:
            if last_moved_token:
                gm.check_captures(last_moved_token)
            gm.next_turn()

        # 描画
        draw_board(screen)
        
        pos_counts = {}
        for t in gm.tokens:
            base_pos = (int(t.display_pos[0]), int(t.display_pos[1]))
            if t.move_queue or t.index == -1:
                pos = base_pos
            else:
                count = pos_counts.get(base_pos, 0)
                pos_counts[base_pos] = count + 1
                pos = (base_pos[0] + count * 4, base_pos[1] + count * 4)

            pygame.draw.circle(screen, COLORS[t.color], pos, TILE//2 - 3)
            pygame.draw.circle(screen, COLORS["BLACK"] if t.index != -1 else COLORS["DARK_GRAY"], pos, TILE//2 - 3, 2)
            
            text_id = font.render(str(t.token_id + 1), True, COLORS["BLACK"] if t.color != "BLUE" else COLORS["WHITE"])
            screen.blit(text_id, (pos[0] - 5, pos[1] - 10))

        # UI描画
        if gm.state != "GAME_OVER":
            current_player_color = gm.players[gm.turn]["color"]
            info_text = f"Mode: {gm.difficulty} | Turn: {current_player_color} ({gm.players[gm.turn]['type']})"
            
            # テキスト背景
            pygame.draw.rect(screen, COLORS["WHITE"], (10, 10, 480, 45))
            text_surface = font.render(info_text, True, COLORS["DARK_GRAY"])
            screen.blit(text_surface, (15, 20))
            
            # 【新機能】サイコロのグラフィック描画
            if gm.state != "ROLLING":
                draw_dice(screen, gm.dice_anim_view_value, 380, 15, size=35)
        else:
            # ゲームオーバー
            overlay = pygame.Surface((SCREEN_SIZE, SCREEN_SIZE), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            pygame.draw.rect(screen, COLORS["WHITE"], (100, 200, 400, 200), 0, 10)
            pygame.draw.rect(screen, COLORS[gm.winner], (100, 200, 400, 200), 5, 10)
            
            win_title = large_font.render("🏆 WINNER 🏆", True, COLORS["BLACK"])
            win_text = large_font.render(f"{gm.winner}!", True, COLORS[gm.winner])
            
            screen.blit(win_title, (SCREEN_SIZE // 2 - win_title.get_width() // 2, 230))
            screen.blit(win_text, (SCREEN_SIZE // 2 - win_text.get_width() // 2, 310))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()

import tkinter as tk
import random
import os
import sys
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps

# --- PyInstaller 相容路徑轉換函式 ---
def resource_path(relative_path):
    """ 取得資源的絕對路徑，支援開發環境與 PyInstaller 打包後的環境 """
    try:
        # PyInstaller 打包後的暫存目錄路徑儲存在 sys._MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # 一般開發環境下使用檔案所在目錄
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- 遊戲常數與路徑 ---
ASSETS_PATH = resource_path("assets")

MINIMAP_SIZE = 180
INITIAL_CELL_SIZE = 60  
MIN_CELL_SIZE = 30      
MAX_CELL_SIZE = 200

SCORE_MAPPING = {"Pawn": 2, "General": 5, "King": 10, "Thief": 1, "Rebel": 2}

# 單位文字設定
UNIT_DATA = {
    "King": {"name": "王"}, 
    "General": {"name": "將"}, 
    "Pawn": {"name": "兵"}, 
    "Thief": {"name": "賊"},
    "Rebel": {"name": "叛"}
}

COLOR_GOLD = "#d4af37"
COLOR_DARK_BG = "#1a1a1a"
COLOR_SIDEBAR = "#2b1b17"
COLOR_THIEF = "#b8860b"    
COLOR_REBEL = "#8d6e63"

class AssetManager:
    """影像處理引擎：負責載入與縮放地形圖"""
    def __init__(self, path):
        self.path = path
        self.raw_imgs = {}
        self.tk_imgs = {}

    def load(self):
        mapping = {
            "t0": "grass.png", "t1": "water.png", "t2": "bridge.png",
            "t3": "castle.png", "t4": "mountain.png", "t5": "forest.png", "t6": "rebel_camp.png",
            "fx_move": "move_fx.png",
            "unit": "unit.png"  # 新增統一的單位圖片
        }
        for key, name in mapping.items():
            fpath = os.path.join(self.path, name)
            try:
                img = Image.open(fpath).convert("RGBA")
                self.raw_imgs[key] = img
                
                # 如果是單位圖片，順便生成一張「沒體力」的灰階版本
                if key == "unit":
                    gray = ImageOps.grayscale(img)
                    gray_rgba = Image.new("RGBA", gray.size)
                    # 利用原本的 alpha 遮罩保留透明背景
                    gray_rgba.paste(gray, (0, 0), img.split()[3]) 
                    self.raw_imgs["unit_ex"] = gray_rgba
            except:
                if key == "fx_move":
                    overlay = Image.new("RGBA", (100, 100), (255, 165, 0, 100)) 
                    self.raw_imgs[key] = overlay
                elif key == "unit":
                    # 如果找不到 unit.png 的預設替代圖
                    self.raw_imgs["unit"] = Image.new("RGBA", (100, 100), (150, 150, 150, 255))
                    self.raw_imgs["unit_ex"] = Image.new("RGBA", (100, 100), (80, 80, 80, 255))
                else:
                    self.raw_imgs[key] = Image.new("RGBA", (100, 100), (80, 80, 80, 255))

    def get(self, key, size):
        size = int(size)
        cache_key = (key, size)
        if cache_key not in self.tk_imgs:
            if key in self.raw_imgs:
                res = self.raw_imgs[key].resize((size, size), Image.Resampling.LANCZOS)
                self.tk_imgs[cache_key] = ImageTk.PhotoImage(res)
        return self.tk_imgs.get(cache_key)

    def clear(self):
        self.tk_imgs.clear()

class EpicWarGameV3:
    def __init__(self, root):
        self.root = root
        self.root.title("2.5 兵將王傳奇 - 打包相容版")
        self.root.geometry("1300x950")
        
        self.assets = AssetManager(ASSETS_PATH)
        self.assets.load()

        self.cell_size = INITIAL_CELL_SIZE
        self.offset_x, self.offset_y = 50, 50
        self.drag_data = {"x": 0, "y": 0}
        self.streak_mode = False 
        self.last_action = None  
        
        self.setup_ui()
        self.reset_game()

        self.canvas.bind("<Configure>", self.on_window_resize)
        self.root.update_idletasks()
        self.draw_all()

    def setup_ui(self):
        self.main_frame = tk.Frame(self.root, bg=COLOR_DARK_BG)
        self.main_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.main_frame, bg="#111", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.sidebar = tk.Frame(self.main_frame, bg=COLOR_SIDEBAR, width=240, relief="raised", bd=3)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="⚔️ 戰局狀態 ⚔️", font=("Microsoft JhengHei", 16, "bold"), bg=COLOR_SIDEBAR, fg=COLOR_GOLD).pack(pady=15)

        self.mode_var = tk.StringVar(value="PvAI (玩家 vs 電腦)")
        self.mode_menu = tk.OptionMenu(self.sidebar, self.mode_var, 
                                       "PvP (玩家 vs 玩家)", "PvAI (玩家 vs 電腦)", 
                                       "AIvP (電腦 vs 玩家)", "AI vs AI (純觀賞)",
                                       command=self.on_mode_change)
        self.mode_menu.config(bg="#44332d", fg="white", font=("Microsoft JhengHei", 10))
        self.mode_menu.pack(pady=5, fill="x", padx=15)
        
        self.status_label = tk.Label(self.sidebar, text="藍軍回合", font=("Microsoft JhengHei", 14, "bold"), bg=COLOR_SIDEBAR, fg="#4444ff")
        self.status_label.pack(pady=10)
        
        self.round_label = tk.Label(self.sidebar, text="", bg=COLOR_SIDEBAR, fg="white", font=("Arial", 11))
        self.round_label.pack()
        self.ap_label = tk.Label(self.sidebar, text="", bg=COLOR_SIDEBAR, fg="#00ff00", font=("Arial", 12, "bold"))
        self.ap_label.pack(pady=5)
        self.score_label = tk.Label(self.sidebar, text="", bg=COLOR_SIDEBAR, fg="white", font=("Arial", 11))
        self.score_label.pack(pady=5)

        btn_style = {"font": ("Microsoft JhengHei", 10), "bg": "#5d4037", "fg": "white", "relief": "flat", "activebackground": COLOR_GOLD}
        self.streak_btn = tk.Button(self.sidebar, text="連擊模式: 關閉", command=self.toggle_streak_mode, **btn_style)
        self.streak_btn.pack(pady=5, fill="x", padx=25)

        self.undo_btn = tk.Button(self.sidebar, text="🔙 悔棋", command=self.undo_move, **btn_style)
        self.undo_btn.pack(pady=5, fill="x", padx=25)
        
        self.end_turn_btn = tk.Button(self.sidebar, text="🛡️ 結束回合", command=self.end_turn_manually, **btn_style)
        self.end_turn_btn.pack(pady=5, fill="x", padx=25)
        
        self.reset_btn = tk.Button(self.sidebar, text="🔄 重新開始", command=self.reset_game, bg="#822", fg="white", relief="flat")
        self.reset_btn.pack(pady=20, fill="x", padx=25)

        self.minimap = tk.Canvas(self.sidebar, width=MINIMAP_SIZE, height=MINIMAP_SIZE, bg="black", highlightthickness=1, highlightbackground=COLOR_GOLD)
        self.minimap.pack(pady=10)

        self.canvas.bind("<Button-1>", self.on_click_left)
        self.canvas.bind("<ButtonPress-3>", self.on_drag_start)
        self.canvas.bind("<B3-Motion>", self.on_drag_motion)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.minimap.bind("<Button-1>", self.on_minimap_action)
        self.minimap.bind("<B1-Motion>", self.on_minimap_action)

    def apply_game_rules(self):
        self.grid_size = 22
        self.max_ap_per_turn = 18  # 已經依照要求修改為 18
        self.castle_size = 3
        self.max_rounds = 15
        self.king_unlock_round = 7 

    def reset_game(self):
        self.apply_game_rules()
        self.turn, self.ap, self.round_number = "blue", self.max_ap_per_turn, 1
        self.scores = {"blue": 0, "red": 0}
        self.selected_unit, self.valid_moves, self.units = None, [], []
        self.grid = [[None for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.terrain = [[0 for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.last_action = None
        self.init_map()
        self.init_units()
        self.status_label.config(text="藍軍回合", fg="#4444ff")
        self.streak_mode = False
        self.update_ui_texts()
        self.draw_all()
        if self.is_current_turn_ai(): self.root.after(800, self.run_ai_turn)

    def init_map(self):
        river_width = 2
        half_w = river_width // 2
        self.river_y_start = self.grid_size // 2 - half_w
        self.river_y_end = self.grid_size // 2 + (half_w - 1)
        for x in range(self.grid_size):
            for y in range(self.river_y_start, self.river_y_end + 1):
                self.terrain[y][x] = 1 
        
        self.bridge_centers = [5, 11, 17] 
        bw = 1 
        for cx in self.bridge_centers:
            for x in range(cx - bw, cx + bw + 1):
                for y in range(self.river_y_start, self.river_y_end + 1):
                    if 0 <= x < self.grid_size: self.terrain[y][x] = 2

        for i in range(self.castle_size):
            for j in range(self.castle_size):
                self.terrain[i][j] = 3
                self.terrain[self.grid_size-1-i][self.grid_size-1-j] = 3
        
        rb_size = 2
        for i in range(rb_size):
            for j in range(rb_size):
                self.terrain[self.grid_size-1-i][j] = 6
                self.terrain[i][self.grid_size-1-j] = 6
                
        self.generate_irregular_terrain(4, 0.05, 4) 
        self.generate_irregular_terrain(5, 0.12, 6) 

    def generate_irregular_terrain(self, terrain_type, coverage, clusters):
        target_tiles = int(self.grid_size * self.grid_size * coverage)
        placed = 0
        for _ in range(clusters):
            if placed >= target_tiles: break
            cx, cy = random.randint(2, self.grid_size-3), random.randint(2, self.grid_size-3)
            stack = [(cx, cy)]
            cluster_size = random.randint(5, 15)
            while stack and len(stack) < cluster_size and placed < target_tiles:
                curr_x, curr_y = stack.pop(random.randint(0, len(stack)-1))
                if self.terrain[curr_y][curr_x] == 0:
                    self.terrain[curr_y][curr_x] = terrain_type
                    placed += 1
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = curr_x + dx, curr_y + dy
                        if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                            if self.terrain[ny][nx] == 0: stack.append((nx, ny))

    def init_units(self):
        self.setup_squad(1, 1, "blue")
        self.setup_squad(self.grid_size-2, self.grid_size-2, "red")
        self.setup_rebel_squad(0, self.grid_size-1) 
        self.setup_rebel_squad(self.grid_size-1, 0) 
        for _ in range(6):
            for _attempt in range(50):
                cx = random.choice(self.bridge_centers)
                tx, ty = cx + random.randint(-1, 1), random.randint(self.river_y_start, self.river_y_end)
                if 0 <= tx < self.grid_size and not self.grid[ty][tx] and self.terrain[ty][tx] == 2:
                    self.add_unit(tx, ty, "neutral", "Thief"); break

    def setup_squad(self, kx, ky, side):
        self.add_unit(kx, ky, side, "King")
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0: continue
                self.add_unit(kx+dx, ky+dy, side, "Pawn")

    def setup_rebel_squad(self, kx, ky):
        for dy in range(2):
            for dx in range(2):
                nx, ny = (kx+dx if kx==0 else kx-dx), (ky-dy if ky==self.grid_size-1 else ky+dy)
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if not self.grid[ny][nx]: self.add_unit(nx, ny, "rebel", "Rebel")

    def add_unit(self, x, y, side, rank):
        inv = 999 if rank == "General" else 0
        u = {"x": x, "y": y, "side": side, "rank": rank, "kills": 0, "moves_this_turn": 0, "invincible_rounds": inv}
        self.units.append(u); self.grid[y][x] = u
        return u

    def get_moves(self, u):
        if u["side"] not in ["neutral", "rebel"]:
            fatigue = (u["y"] > self.river_y_end if u["side"]=="blue" else u["y"] < self.river_y_start)
            if u["moves_this_turn"] >= (2 if fatigue else 3): return [] 
        
        moves = []
        cost_m = 2 if u["moves_this_turn"] > 0 else 1 
        aura = any(un["side"] == u["side"] and un["rank"] in ["King", "General"] and un != u and abs(un["x"]-u["x"]) <= 5 and abs(un["y"]-u["y"]) <= 5 for un in self.units)
        
        in_forest = (self.terrain[u["y"]][u["x"]] == 5)
        limit = 1 if (in_forest and u["side"] != "rebel") else (2 if (u["rank"] in ["King", "General", "Rebel"] or aura) else 1)
        
        for dy in range(-limit, limit + 1):
            for dx in range(-limit, limit + 1):
                if dx == 0 and dy == 0: continue
                tx, ty = u["x"] + dx, u["y"] + dy
                if 0 <= tx < self.grid_size and 0 <= ty < self.grid_size:
                    if self.terrain[ty][tx] in [1, 4]: continue 
                    if u["rank"] == "King" and self.round_number < self.king_unlock_round and self.terrain[ty][tx] != 3: continue
                    target = self.grid[ty][tx]
                    if target:
                        if max(abs(dx), abs(dy)) > 1: continue 
                        if target["rank"] == "King" and u["rank"] == "General": continue
                        cost_a = 5 if self.streak_mode else 3
                        if target["side"] != u["side"] and (u["side"] in ["neutral", "rebel"] or self.ap >= cost_a) and target.get("invincible_rounds", 0) <= 0:
                            moves.append((tx, ty))
                    elif u["side"] in ["neutral", "rebel"] or self.ap >= cost_m: 
                        moves.append((tx, ty))
        return moves

    def execute_move(self, u, lx, ly):
        target = self.grid[ly][lx]
        is_npc = (u["side"] in ["neutral", "rebel"])
        if not is_npc:
            self.last_action = {"unit": u, "old_pos": (u["x"], u["y"]), "old_ap": self.ap, "old_moves_count": u["moves_this_turn"], 
                                "old_rank": u["rank"], "old_kills": u["kills"], "old_invincible": u.get("invincible_rounds", 0),
                                "target_unit": target, "old_scores": self.scores.copy(), "drowned": False}
        
        is_stk = False
        if target: 
            if not is_npc:
                self.ap -= (5 if self.streak_mode else 3)
                self.scores[self.turn] += SCORE_MAPPING.get(target["rank"], 0)
            if u["rank"] == "General": u["invincible_rounds"] = 0
            if target["rank"] == "King": 
                self.turn = "over"
                messagebox.showinfo("戰鬥結束", f"{'藍軍' if target['side'] == 'blue' else '紅軍'}國王戰死！")
            if target in self.units: self.units.remove(target)
            u["kills"] += 1; is_stk = True
            
            if u["rank"] == "Pawn" and u["side"] in ["blue", "red"]:
                if not any(un["side"] == u["side"] and un["rank"] == "General" for un in self.units):
                    u["rank"] = "General"; u["invincible_rounds"] = 999
        else: 
            if not is_npc: self.ap -= (1 if u["moves_this_turn"] == 0 else 2)
        
        self.grid[u["y"]][u["x"]] = None; u["x"], u["y"] = lx, ly; self.grid[ly][lx] = u; u["moves_this_turn"] += 1
        
        fatigue = (u["y"] > self.river_y_end if u["side"]=="blue" else u["y"] < self.river_y_start)
        if not is_npc and self.terrain[ly][lx] == 1 and (u["moves_this_turn"] >= (2 if fatigue else 3) or self.ap <= 0):
            self.units.remove(u); self.grid[ly][lx] = None
            if not is_npc: self.last_action["drowned"] = True
        
        if self.turn != "over":
            can_stk = (not is_npc and not self.last_action.get("drowned", False) and is_stk and self.streak_mode and u["moves_this_turn"] < (2 if fatigue else 3) and self.ap > 0)
            if can_stk: self.valid_moves = self.get_moves(u)
            else: self.selected_unit, self.valid_moves = None, []
            
        self.update_ui_texts(); self.draw_all()
        if not is_npc: self.root.after(150, self.check_auto_end_turn)

    def undo_move(self):
        if not self.last_action or self.turn == "over": return
        act = self.last_action; u = act["unit"]
        if act.get("drowned", False): self.units.append(u)
        self.grid[u["y"]][u["x"]] = None; u["x"], u["y"] = act["old_pos"]; self.grid[u["y"]][u["x"]] = u
        u["moves_this_turn"], u["rank"], u["kills"], u["invincible_rounds"] = act["old_moves_count"], act["old_rank"], act["old_kills"], act["old_invincible"]
        if act["target_unit"]: t = act["target_unit"]; self.units.append(t); self.grid[t["y"]][t["x"]] = t
        self.ap, self.scores, self.last_action = act["old_ap"], act["old_scores"], None
        self.update_ui_texts(); self.draw_all()

    def run_npc_turns(self):
        for faction in ["rebel", "neutral"]:
            self.turn = faction
            for u in [un for un in self.units if un["side"] == faction]:
                u["moves_this_turn"] = 0
                moves = self.get_moves(u)
                if not moves: continue
                targets = [en for en in self.units if en["side"] in ["blue", "red"]]
                if not targets: break 
                target_enemy = min(targets, key=lambda e: abs(e["x"]-u["x"]) + abs(e["y"]-u["y"]))
                attack_moves = [m for m in moves if self.grid[m[1]][m[0]]]
                best = max(attack_moves, key=lambda m: SCORE_MAPPING.get(self.grid[m[1]][m[0]]["rank"], 0)) if attack_moves else min(moves, key=lambda m: abs(m[0]-target_enemy["x"]) + abs(m[1]-target_enemy["y"]))
                self.execute_move(u, best[0], best[1])
        if self.turn != "over":
            self.turn = "blue"; self.ap = self.max_ap_per_turn
            for u in self.units: 
                if u["side"] == "blue": u["moves_this_turn"] = 0
            self.status_label.config(text="藍軍回合", fg="#4444ff")
            self.update_ui_texts(); self.draw_all()
            if self.is_current_turn_ai(): self.root.after(400, self.run_ai_turn)

    def run_ai_turn(self):
        if not self.is_current_turn_ai() or self.turn in ["over", "neutral", "rebel"] or self.ap <= 0: return
        fatigue_check = lambda u: (u["y"] > self.river_y_end if u["side"]=="blue" else u["y"] < self.river_y_start)
        my_units = [u for u in self.units if u["side"] == self.turn and u["moves_this_turn"] < (2 if fatigue_check(u) else 3)]
        if not my_units: self.end_turn(); return
        en_s = "red" if self.turn == "blue" else "blue"
        en_king = next((u for u in self.units if u["side"] == en_s and u["rank"] == "King"), None)
        best, high = None, -999999
        for u in random.sample(my_units, min(len(my_units), 20)):
            for mx, my in self.get_moves(u):
                s = random.randint(0, 30)
                target = self.grid[my][mx]
                if target: s += {"King": 50000, "General": 2000, "Pawn": 600, "Thief": 300, "Rebel": 400}.get(target["rank"], 0)
                if en_king: s += (self.grid_size*2 - (abs(mx - en_king["x"]) + abs(my - en_king["y"]))) * 20
                if s > high: high, best = s, (u, mx, my)
        if best: self.execute_move(*best)
        else: self.end_turn()

    def draw_all(self):
        self.canvas.delete("all")
        vw, vh = self.canvas.winfo_width(), self.canvas.winfo_height()
        if vw <= 1: return 

        for y in range(self.grid_size):
            for x in range(self.grid_size):
                tid = self.terrain[y][x]
                px, py = x*self.cell_size + self.offset_x, y*self.cell_size + self.offset_y
                if -self.cell_size < px < vw and -self.cell_size < py < vh:
                    img = self.assets.get(f"t{tid}", self.cell_size)
                    self.canvas.create_image(px, py, image=img, anchor="nw", tags="layer_terrain")

        if self.selected_unit:
            fx_img = self.assets.get("fx_move", self.cell_size)
            for mx, my in self.valid_moves:
                px, py = mx*self.cell_size + self.offset_x, my*self.cell_size + self.offset_y
                self.canvas.create_image(px, py, image=fx_img, anchor="nw", tags="layer_highlight")
                if self.grid[my][mx]:
                    self.canvas.create_rectangle(px+2, py+2, px+self.cell_size-2, py+self.cell_size-2, outline="#ff2222", width=3, tags="layer_highlight")

        for u in self.units:
            ux, uy = u["x"]*self.cell_size + self.offset_x, u["y"]*self.cell_size + self.offset_y
            if -self.cell_size < ux < vw and -self.cell_size < uy < vh:
                
                # --- [修正] 灰階模式套用到全體陣營 (紅藍、賊、叛) ---
                fatigue = (u["y"] > self.river_y_end if u["side"]=="blue" else u["y"] < self.river_y_start)
                
                # 判斷是否耗盡體力
                if u["side"] in ["blue", "red"]:
                    # 玩家陣營依舊是 2~3 次行動
                    is_ex = u["moves_this_turn"] >= (2 if fatigue else 3)
                else:
                    # 第三方勢力 (賊、叛) 行動過 1 次就變灰
                    is_ex = u["moves_this_turn"] >= 1
                
                # 1. 決定要用哪張圖：體力耗盡時使用灰階圖片 (unit_ex)
                img_key = "unit_ex" if is_ex else "unit"
                img = self.assets.get(img_key, self.cell_size)
                
                # 2. 繪製單位 PNG
                self.canvas.create_image(ux, uy, image=img, anchor="nw", tags="layer_unit")
                
                # 3. [修正] 繪製兵種文字 (極限縮小 + 灰階套用)
                text_c = "white"
                
                # --- [修正] 如果是灰階模式，文字也變灰色 ---
                if is_ex:
                    text_c = "#aaaaaa"
                elif u["side"] == "blue": 
                    text_c = "#aaaaff"
                elif u["side"] == "red": 
                    text_c = "#ffaaaa"
                elif u["side"] == "neutral": 
                    text_c = COLOR_THIEF
                elif u["side"] == "rebel": 
                    text_c = COLOR_REBEL

                # --- [修正] font size 比例從 0.4 縮小至 0.15 (極限縮小) ---
                self.canvas.create_text(ux+self.cell_size/2, uy+self.cell_size/2, 
                                        text=UNIT_DATA[u['rank']]['name'], 
                                        fill=text_c, 
                                        font=("Microsoft JhengHei", int(self.cell_size * 0.15), "bold"), 
                                        tags="layer_unit")

        self.canvas.tag_raise("layer_terrain")
        self.canvas.tag_raise("layer_highlight")
        self.canvas.tag_raise("layer_unit")
        self.update_minimap()

    def update_minimap(self):
        self.minimap.delete("all"); s = MINIMAP_SIZE / self.grid_size
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                tid = self.terrain[y][x]
                colors = ["#4e7d32", "#1e3a8a", "#525252", "#333333", "#4e342e", "#1b5e20", "#8d6e63"]
                self.minimap.create_rectangle(x*s, y*s, (x+1)*s, (y+1)*s, fill=colors[tid], outline="")
        for u in self.units: 
            uc = "#44f" if u["side"]=="blue" else ("#f44" if u["side"]=="red" else "gray")
            self.minimap.create_rectangle(u["x"]*s, u["y"]*s, (u["x"]+1)*s, (u["y"]+1)*s, fill=uc, outline="")
        vw, vh = self.canvas.winfo_width(), self.canvas.winfo_height()
        if vw > 1:
            x1, y1 = (-self.offset_x / (self.grid_size * self.cell_size)) * MINIMAP_SIZE, (-self.offset_y / (self.grid_size * self.cell_size)) * MINIMAP_SIZE
            x2, y2 = x1 + (vw / (self.grid_size * self.cell_size)) * MINIMAP_SIZE, y1 + (vh / (self.grid_size * self.cell_size)) * MINIMAP_SIZE
            self.minimap.create_rectangle(x1, y1, x2, y2, outline="white", width=1)

    def update_ui_texts(self):
        self.ap_label.config(text=f"剩餘 AP: {self.ap}")
        self.round_label.config(text=f"回合: {self.round_number} / {self.max_rounds}")
        self.score_label.config(text=f"藍: {self.scores['blue']}  |  紅: {self.scores['red']}")
        self.undo_btn.config(state="normal" if (self.last_action and not self.is_current_turn_ai()) else "disabled")

    def toggle_streak_mode(self):
        self.streak_mode = not self.streak_mode
        self.streak_btn.config(bg="#aa00ff" if self.streak_mode else "#5d4037", text=f"連擊模式: {'開啟' if self.streak_mode else '關閉'}")

    def on_click_left(self, event):
        if self.turn in ["over", "neutral", "rebel"] or self.is_current_turn_ai(): return 
        lx, ly = int((event.x - self.offset_x) // self.cell_size), int((event.y - self.offset_y) // self.cell_size)
        if not (0 <= lx < self.grid_size and 0 <= ly < self.grid_size): return
        target = self.grid[ly][lx]
        if target and target["side"] == self.turn:
            self.selected_unit, self.valid_moves = target, self.get_moves(target)
            self.draw_all()
        elif self.selected_unit and (lx, ly) in self.valid_moves:
            self.execute_move(self.selected_unit, lx, ly)

    def is_current_turn_ai(self):
        m = self.mode_var.get()
        return (m == "AI vs AI (純觀賞)" or (m == "PvAI (玩家 vs 電腦)" and self.turn == "red") or (m == "AIvP (電腦 vs 玩家)" and self.turn == "blue"))

    def check_auto_end_turn(self):
        if self.turn != "over" and (self.ap <= 0 or not any(self.get_moves(u) for u in self.units if u["side"] == self.turn)): self.end_turn()
        elif self.turn != "over" and self.is_current_turn_ai(): self.run_ai_turn()

    def end_turn_manually(self):
        if self.turn in ["over", "neutral", "rebel"] or self.is_current_turn_ai(): return
        self.end_turn()

    def end_turn(self):
        if self.turn == "over": return
        for u in [un for un in self.units if self.terrain[un["y"]][un["x"]] == 1 and un["side"] not in ["neutral", "rebel"]]: 
            self.grid[u["y"]][u["x"]] = None; self.units.remove(u)
        if self.turn == "blue": self.turn = "red"
        elif self.turn == "red":
            self.round_number += 1
            if self.round_number > self.max_rounds: self.check_winner(); return
            self.status_label.config(text="第三方勢力行動!", fg="white"); self.turn = "rebel"
            self.root.after(600, self.run_npc_turns); return
        self.ap = self.max_ap_per_turn 
        for u in self.units: 
            if u["side"] == self.turn: u["moves_this_turn"] = 0 
        self.selected_unit = None
        self.status_label.config(text=f"{'紅' if self.turn=='red' else '藍'}軍回合", fg="#ff4444" if self.turn=="red" else "#4444ff")
        self.update_ui_texts(); self.draw_all()
        if self.is_current_turn_ai(): self.root.after(400, self.run_ai_turn)

    def check_winner(self):
        self.turn = "over"; b, r = self.scores["blue"], self.scores["red"]
        msg = "藍軍獲勝！" if b > r else ("紅軍獲勝！" if r > b else "平手！")
        messagebox.showinfo("作戰結束", f"時間到！\n藍：{b} 紅：{r}\n{msg}")

    def on_mode_change(self, *args): self.reset_game()
    def on_window_resize(self, e): self.keep_in_bounds(); self.draw_all()
    def on_zoom(self, e):
        self.assets.clear()
        f = 1.1 if e.delta > 0 else 0.9
        mx, my = (e.x - self.offset_x) / self.cell_size, (e.y - self.offset_y) / self.cell_size
        self.cell_size = max(MIN_CELL_SIZE, min(MAX_CELL_SIZE, self.cell_size * f))
        self.offset_x, self.offset_y = e.x - mx * self.cell_size, e.y - my * self.cell_size
        self.keep_in_bounds(); self.draw_all()

    def on_drag_start(self, e): self.drag_data = {"x": e.x, "y": e.y}
    def on_drag_motion(self, e):
        self.offset_x += e.x - self.drag_data["x"]; self.offset_y += e.y - self.drag_data["y"]
        self.drag_data = {"x": e.x, "y": e.y}; self.keep_in_bounds(); self.draw_all()

    def on_minimap_action(self, e):
        vw, vh = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.offset_x = (vw/2) - (e.x / MINIMAP_SIZE) * (self.grid_size * self.cell_size)
        self.offset_y = (vh/2) - (e.y / MINIMAP_SIZE) * (self.grid_size * self.cell_size)
        self.keep_in_bounds(); self.draw_all()

    def keep_in_bounds(self):
        vw, vh = self.canvas.winfo_width(), self.canvas.winfo_height()
        if vw <= 1: return
        mw, mh = self.grid_size * self.cell_size, self.grid_size * self.cell_size
        self.offset_x = max(vw - mw, min(0, self.offset_x)) if mw > vw else (vw - mw) / 2
        self.offset_y = max(vh - mh, min(0, self.offset_y)) if mh > vh else (vh - mh) / 2

if __name__ == "__main__":
    if not os.path.exists(ASSETS_PATH):
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("路徑錯誤", f"找不到 Assets 目錄！\n路徑: {ASSETS_PATH}\n請確認打包指令是否包含 --add-data")
    else:
        root = tk.Tk()
        game = EpicWarGameV3(root)
        root.mainloop()
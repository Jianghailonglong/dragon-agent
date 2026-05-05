"""游戏配置常量"""

# 窗口设置
CELL_SIZE = 30          # 每个格子的像素大小
GRID_WIDTH = 25         # 网格宽度（格子数）
GRID_HEIGHT = 25        # 网格高度（格子数）
WINDOW_WIDTH = CELL_SIZE * GRID_WIDTH
WINDOW_HEIGHT = CELL_SIZE * GRID_HEIGHT + 60  # 额外60像素用于显示分数栏
FPS = 60                # 帧率

# 颜色定义 (R, G, B)
BLACK       = (0, 0, 0)
WHITE       = (255, 255, 255)
GRAY        = (40, 40, 40)
DARK_GRAY   = (30, 30, 30)
GREEN       = (0, 200, 0)
DARK_GREEN  = (0, 150, 0)
RED         = (220, 30, 30)
GOLD        = (255, 215, 0)
BLUE        = (50, 120, 220)
SCORE_BG    = (25, 25, 35)

# 蛇的初始设置
SNAKE_INIT_LENGTH = 3
SNAKE_START_X = 12
SNAKE_START_Y = 12

# 速度设置（毫秒/每步）
INITIAL_SPEED = 150     # 初始速度（越大越慢）
MIN_SPEED = 60          # 最快速度
SPEED_INCREMENT = 5     # 每吃一个食物加速的毫秒数

# 分数设置
SCORE_PER_FOOD = 10

# 游戏状态
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_GAMEOVER = "gameover"

# 最高分文件
HIGHSCORE_FILE = "highscore.json"

# 方向
UP    = (0, -1)
DOWN  = (0, 1)
LEFT  = (-1, 0)
RIGHT = (1, 0)

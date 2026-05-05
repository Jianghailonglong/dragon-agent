"""蛇类 - 管理蛇的移动、生长、碰撞"""

import pygame
from settings import (
    CELL_SIZE, GRID_WIDTH, GRID_HEIGHT,
    GREEN, DARK_GREEN, BLACK,
    SNAKE_INIT_LENGTH, SNAKE_START_X, SNAKE_START_Y,
    UP, DOWN, LEFT, RIGHT
)


class Snake:
    def __init__(self):
        """初始化蛇"""
        self.reset()

    def reset(self):
        """重置蛇到初始状态"""
        self.direction = RIGHT
        self.next_direction = RIGHT
        # 蛇身：列表第一个元素是蛇头
        self.body = []
        for i in range(SNAKE_INIT_LENGTH):
            self.body.append((SNAKE_START_X - i, SNAKE_START_Y))
        self.grow_pending = False
        self.alive = True

    def set_direction(self, new_direction):
        """设置蛇的移动方向（防止180度掉头）"""
        # 不允许反向移动
        opposite = (-self.direction[0], -self.direction[1])
        if new_direction != opposite:
            self.next_direction = new_direction

    def move(self):
        """移动蛇一格，返回是否成功"""
        if not self.alive:
            return False

        # 更新方向
        self.direction = self.next_direction

        # 计算新的头部位置
        head_x, head_y = self.body[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # 检查是否撞墙
        nx, ny = new_head
        if nx < 0 or nx >= GRID_WIDTH or ny < 0 or ny >= GRID_HEIGHT:
            self.alive = False
            return False

        # 检查是否撞到自身
        if new_head in self.body:
            self.alive = False
            return False

        # 移动：在头部添加新位置
        self.body.insert(0, new_head)

        # 如果需要增长，保留尾部；否则移除尾部
        if self.grow_pending:
            self.grow_pending = False
        else:
            self.body.pop()

        return True

    def grow(self):
        """标记蛇需要增长"""
        self.grow_pending = True

    def get_head(self):
        """获取蛇头位置"""
        return self.body[0]

    def draw(self, surface):
        """绘制蛇"""
        for i, (x, y) in enumerate(self.body):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE + 60, CELL_SIZE, CELL_SIZE)

            if i == 0:
                # 蛇头 - 亮绿色
                pygame.draw.rect(surface, GREEN, rect)
                pygame.draw.rect(surface, BLACK, rect, 1)
                # 画眼睛
                self._draw_eyes(surface, x, y)
            else:
                # 蛇身 - 渐变深绿色
                ratio = i / len(self.body)
                g = max(80, int(200 - ratio * 120))
                color = (0, g, 0)
                inner_rect = rect.inflate(-4, -4)
                pygame.draw.rect(surface, color, inner_rect)
                pygame.draw.rect(surface, DARK_GREEN, inner_rect, 1)

    def _draw_eyes(self, surface, x, y):
        """画蛇的眼睛"""
        cx = x * CELL_SIZE + CELL_SIZE // 2
        cy = y * CELL_SIZE + 60 + CELL_SIZE // 2
        dx, dy = self.direction

        # 两只眼睛的位置
        eye_offset = 5
        if dx == 0:  # 上下移动
            e1 = (cx - eye_offset, cy + dy * 4)
            e2 = (cx + eye_offset, cy + dy * 4)
        else:  # 左右移动
            e1 = (cx + dx * 4, cy - eye_offset)
            e2 = (cx + dx * 4, cy + eye_offset)

        pygame.draw.circle(surface, WHITE, e1, 3)
        pygame.draw.circle(surface, WHITE, e2, 3)
        pygame.draw.circle(surface, BLACK, e1, 1)
        pygame.draw.circle(surface, BLACK, e2, 1)

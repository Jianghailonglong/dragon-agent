"""食物类 - 随机生成食物，渲染显示"""

import random
import pygame
from settings import CELL_SIZE, GRID_WIDTH, GRID_HEIGHT, RED, GOLD, BLACK


class Food:
    def __init__(self):
        """初始化食物"""
        self.position = (0, 0)
        self.special = False  # 特殊食物（金色，双倍分数）
        self.special_timer = 0

    def spawn(self, snake_body):
        """在不与蛇身重叠的位置生成新食物"""
        available = []
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                if (x, y) not in snake_body:
                    available.append((x, y))

        if available:
            self.position = random.choice(available)
            # 10% 概率生成特殊食物
            self.special = random.random() < 0.1
            self.special_timer = 0

    def draw(self, surface):
        """绘制食物"""
        x, y = self.position
        rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE + 60, CELL_SIZE, CELL_SIZE)

        if self.special:
            # 特殊食物 - 金色，带闪烁效果
            self.special_timer += 1
            alpha = abs((self.special_timer % 30) - 15) / 15
            r = int(255 * alpha + 200 * (1 - alpha))
            g = int(215 * alpha + 150 * (1 - alpha))
            color = (r, g, 0)
            inner_rect = rect.inflate(-6, -6)
            pygame.draw.rect(surface, color, inner_rect)
            # 星星标记
            cx = x * CELL_SIZE + CELL_SIZE // 2
            cy = y * CELL_SIZE + 60 + CELL_SIZE // 2
            pygame.draw.circle(surface, GOLD, (cx, cy), 5)
            pygame.draw.circle(surface, BLACK, (cx, cy), 5, 1)
        else:
            # 普通食物 - 红色苹果
            inner_rect = rect.inflate(-6, -6)
            pygame.draw.rect(surface, RED, inner_rect)
            pygame.draw.rect(surface, BLACK, inner_rect, 1)
            # 小叶子
            cx = x * CELL_SIZE + CELL_SIZE // 2
            leaf_rect = pygame.Rect(cx - 2, y * CELL_SIZE + 60 + 2, 6, 4)
            pygame.draw.rect(surface, (0, 150, 0), leaf_rect)

    def get_score(self):
        """获取该食物的分值"""
        return 20 if self.special else 10

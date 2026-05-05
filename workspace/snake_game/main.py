"""贪吃蛇游戏 - 主入口"""

import sys
import os

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import Game


def main():
    """启动贪吃蛇游戏"""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()

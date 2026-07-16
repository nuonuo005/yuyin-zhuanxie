from __future__ import annotations

import unittest

from yuyin_zhuanxie.text_tools import convert_chinese_numbers


class TextToolsTests(unittest.TestCase):
    def test_converts_clear_numbers(self) -> None:
        self.assertEqual(convert_chinese_numbers("一百二十三"), "123")
        self.assertEqual(convert_chinese_numbers("三十个"), "30个")
        self.assertEqual(convert_chinese_numbers("一二三"), "123")

    def test_preserves_common_non_numeric_words(self) -> None:
        self.assertEqual(convert_chinese_numbers("万一下雨怎么办"), "万一下雨怎么办")
        self.assertEqual(convert_chinese_numbers("千万不要删除"), "千万不要删除")
        self.assertEqual(convert_chinese_numbers("十全十美"), "十全十美")


if __name__ == "__main__":
    unittest.main()

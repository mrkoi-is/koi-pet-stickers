# 皮皮：六风格完整示例

本示例使用同一张“皮皮”照片，分别运行 `koi-pet-stickers` 的六种内置风格。
图片展示的是最终 16 张透明 PNG 的棋盘格预览；每次生成存在合理随机差异。

## 输入

<p align="center">
  <img src="assets/input-pipi.jpg" width="320" alt="皮皮输入照片">
</p>

- 宠物名字：`皮皮`
- 输入照片：1 张
- 表情数量：固定 16 张
- 排列顺序：4×4，按行依次为开心、收到、生气、委屈、早安、晚安、谢谢、
  抱抱、加油、好的、不行、怎么啦、吃饭啦、想你啦、冲鸭、拜拜

## 默认调用

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”生成表情包。
```

未指定风格时使用 `q-cute-handdrawn`（Q萌手绘贴纸）。

## 六风格提示词与结果

### 1. Q萌手绘贴纸

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”，采用“Q萌手绘贴纸”风格生成表情包。
```

![Q萌手绘贴纸](assets/q-cute-handdrawn.png)

### 2. 极简扁平 Emoji

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”，采用“极简扁平 Emoji”风格生成表情包。
```

![极简扁平 Emoji](assets/flat-emoji.png)

### 3. 粗线漫画大字

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”，采用“粗线漫画大字”风格生成表情包。
```

![粗线漫画大字](assets/bold-comic.png)

### 4. 蜡笔手帐涂鸦

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”，采用“蜡笔手帐涂鸦”风格生成表情包。
```

![蜡笔手帐涂鸦](assets/crayon-journal.png)

### 5. 稚拙墨线水彩

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”，采用“稚拙墨线水彩”风格生成表情包。
```

![稚拙墨线水彩](assets/naive-ink-watercolor.png)

### 6. 粗墨怪萌水彩

```text
使用 $koi-pet-stickers，用我上传的宠物照片和名字“皮皮”，采用“粗墨怪萌水彩”风格生成表情包。
```

![粗墨怪萌水彩](assets/bold-ink-caricature.png)

## 交付检查

六次测试均满足默认切图 gate：

- `extract_grid.py` 返回 `ok: true`
- 每种风格输出正好 16 张非空 RGBA PNG
- 角色、文字、耳朵、爪子、尾巴、道具和装饰没有实际裁断
- 没有错格、邻格残片、不透明白底板或透明化误删

身份、风格、动作、情绪和文字差异属于默认非阻断观察；若需要企业级完整包，
再启用严格身份、文字和视觉 QA。

# Photo Video Organizer

一个用于整理本地照片和视频库的 Codex skill。它可以按文件时间戳把图片、视频归档到年份/月目录，安全处理同名文件和重复文件，并支持把媒体文件批量重命名为日期格式。

适合整理手机导出的相册、外置硬盘照片库、混乱的图片视频文件夹。

## 功能

- 按时间戳归档图片和视频
- 默认目录格式：`_YYYY/M月`
- 保留已有目录格式，不强行改目录名
- 跳过已经在正确位置的媒体文件
- 支持按日期重命名：`YYYYMMDD.ext`
- 同一天多个文件自动编号：`20250501-001.HEIC`
- 同名不同内容时自动改名保留
- 目标位置已有完全相同文件时可安全去重
- 支持 macOS `._filename` 伴随文件跟随移动或改名
- 支持 dry-run 预览，避免误操作

## 目录示例

整理前：

```text
相册/
├── IMG_0012.HEIC
├── IMG_0013.HEIC
├── video_01.MOV
└── 其他文件.docx
```

整理后：

```text
相册/
├── _2025/
│   └── 5月/
│       ├── 20250501.HEIC
│       ├── 20250501-001.HEIC
│       └── 20250502.MOV
└── 其他文件.docx
```

## 安装

把整个 `photo-video-organizer` 文件夹放到 Codex 可发现的 skills 目录中，例如：

```bash
~/.codex/skills/photo-video-organizer
```

或项目级 skill 目录：

```bash
.agents/skills/photo-video-organizer
```

目录结构应类似：

```text
photo-video-organizer/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
└── scripts/
    └── organize_media.py
```

## 最简单的触发方式

在 Codex 里直接说：

```text
使用 photo-video-organizer 整理这个相册目录：/路径/到/相册
```

也可以说：

```text
帮我用照片视频整理 skill，把 /Volumes/sky/相册/xx 按时间归档并重命名
```

## 命令行用法

脚本路径：

```bash
scripts/organize_media.py
```

先 dry-run 预览，不修改文件：

```bash
python3 scripts/organize_media.py \
  --root "/Volumes/sky/相册/xx" \
  --archive \
  --dry-run
```

按 `_年份/月月` 归档：

```bash
python3 scripts/organize_media.py \
  --root "/Volumes/sky/相册/xx" \
  --archive
```

归档并去掉目标位置已有的完全相同重复文件：

```bash
python3 scripts/organize_media.py \
  --root "/Volumes/sky/相册/xx" \
  --archive \
  --dedupe-identical
```

按日期重命名：

```bash
python3 scripts/organize_media.py \
  --root "/Volumes/sky/相册/xx" \
  --rename
```

先归档，再按日期重命名：

```bash
python3 scripts/organize_media.py \
  --root "/Volumes/sky/相册/xx" \
  --archive \
  --rename \
  --dedupe-identical
```

## 参数说明

| 参数                  | 说明                                           |
| --------------------- | ---------------------------------------------- |
| `--root PATH`         | 媒体库根目录，必填                             |
| `--archive`           | 按年份/月目录归档媒体文件                      |
| `--rename`            | 按时间戳把媒体文件重命名为日期格式             |
| `--dry-run`           | 只预览，不实际移动、删除或改名                 |
| `--dedupe-identical`  | 目标位置已有字节完全一致文件时，删除源重复文件 |
| `--include-sidecars`  | 让 macOS `._filename` 伴随文件跟随移动或改名   |
| `--year-prefix "_"`   | 年份目录前缀，默认生成 `_2026`                 |
| `--month-suffix "月"` | 月份目录后缀，默认生成 `1月`                   |
| `--extensions`        | 自定义要处理的扩展名，逗号分隔                 |

## 支持的媒体类型

默认处理：

```text
jpg, jpeg, png, heic, heif, tif, tiff, webp, gif, bmp,
mp4, mov, m4v, avi, 3gp, mts, mkv
```

默认不处理 `.aae`，因为它通常是 iPhone 照片编辑记录，不是媒体本体。

## 时间戳规则

脚本优先使用文件创建时间；如果系统或文件系统没有创建时间，则回退到文件修改时间。

这对 macOS 外置硬盘和手机导出照片比较实用，但如果文件曾被复制、下载或重新生成，文件系统时间可能不等于真实拍摄时间。需要严格使用 EXIF 拍摄时间时，可以在后续版本扩展。

## 安全策略

- 不覆盖已有文件
- 已在正确目录的文件会跳过
- 同名但内容不同的文件会自动加编号保留
- 完全相同的重复文件只有在使用 `--dedupe-identical` 时才会删除源文件
- 大批量改名使用两步改名，避免文件名互相占用
- 建议任何真实整理前先运行 `--dry-run`

## 示例输出

```text
scanned_media=22687
archive_summary
total_media=22687
already_correct=14690
moved=7997
renamed_for_collision=141
deduped_identical=4527
moved_sidecars=0
errors=0
```


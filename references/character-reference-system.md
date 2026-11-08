# 角色定稿参考系统

以当前生效的角色登记表为唯一角色身份来源：用户运行 `scripts/setup_config.py` 后生成在 `$IP_COURSE_HOME/character-reference/registry.json`（默认 `~/.config/ip-course-videos/`）；未配置时只有 `assets/character-reference/registry.json` 里的示例占位角色，不得用于正式生成。`init_project.py` 会把实际使用的登记表路径写进 `project.json` 的 `characterRegistry`。开始背景与参演人物规划前运行 `validate_character_registry.py --registry <该路径>`。

## 使用规则

- 参演表包含某角色时，每次生成该镜头都附带该角色的 `canonicalPath`；IP 人物通常为必选。
- 只允许 `status: approved` 且哈希匹配的角色进入生成。`pending-user-asset` 必须暂停并请用户提供或确认定稿图。
- 定稿图锁定身份、配色和画风，不锁定场景、动作或构图。不得用带复杂场景的成片帧替代角色定稿图。
- 群众也属于受控角色资产，不能每个镜头随机换成写实人物或不同画风。
- 更换定稿图必须提升版本、更新哈希并重新审核受影响的 A-roll；禁止静默覆盖。

## 自动检查边界

脚本只检查文件、状态、哈希、版本和路径，不判断眼睛、手部、相似度或画风。视觉正确性全部进入 A-roll 人工审核。

## 用户资产配置

- 角色图、外观特征（`identityInvariants`）都写在用户自己的 `config.json` 里，不放进 skill 目录。
- `role: required-host` 的角色是主讲 IP；其他角色（吉祥物、配角、群众等）在 `extraCharacters` 里按需添加，没配置图片的角色不会进登记表。
- 模板用到的图片按 `assets/character-slots.json` 的插槽名放在项目的 `assets/ip-reference/` 下；`init_project.py` 会自动从用户配置复制过去，没配置的插槽按 fallback 用主角图或透明图代替。
- 更换角色图后重新运行 `setup_config.py`，它会更新哈希；已审核的 A-roll 需要重新审核。

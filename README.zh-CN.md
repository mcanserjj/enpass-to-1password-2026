# Enpass to 1Password 2026

这是一个仅依赖 Python 3 标准库的跨平台命令行工具，用于把 Enpass 导出的
JSON 转换为可通过 1Password 网页导入器导入的 CSV。

工具不会编造缺失字段，也不会静默丢弃不受支持的类别：满足 1Password
必填条件的条目会生成登录或信用卡；其他类别及字段不完整的条目会生成
安全备注，并在备注中保留原始 Enpass 类别、字段、文件夹、状态和可识别的
密码历史。

## 生成内容

- `logins.csv`：同时具有用户名、密码和网站的登录条目。
- `credit_cards.csv`：同时具有卡号和到期日的信用卡。
- `secure_notes.csv`：其余所有类别以及字段不完整的登录/信用卡。
- `attachments/`：从 JSON 提取的附件；CSV 无法导入附件，需要手工添加。
- `conversion-report.json`：输入输出数量、降级原因和附件提取状态。

每个源条目只进入一个 CSV。CSV 使用带 BOM 的 UTF-8 编码，并正确处理逗号、
双引号和多行内容。

## 环境要求

- Python 3.10 或更高版本
- Enpass JSON 导出文件

无需安装第三方 Python 包。

## 转换

```shell
python enpass_to_1password.py Enpass.json output
```

如果输出目录不是空目录，脚本会停止，避免覆盖或混入旧的明文迁移数据。
请改用一个新的空目录。

运行测试：

```shell
python -m unittest discover -s tests -v
```

## 导入 1Password

1. 使用浏览器登录 1Password.com。
2. 选择右上角的姓名，然后选择“导入数据”>“CSV 文件”。
3. 导入 `logins.csv`，类型选择“登录”，并映射各列。
4. 导入 `credit_cards.csv`，类型选择“信用卡”，并映射各列。
5. 导入 `secure_notes.csv`，类型选择“安全备注”，并映射各列。
6. 对照 `conversion-report.json` 核对源条目数和输出条目数。
7. 逐项验证重要密码、信用卡以及每一个 TOTP 动态验证码。
8. 如有附件，根据备注中的路径手工添加。
9. 验证完成后删除未加密的 JSON、CSV、报告和附件，并清空回收站。

如果当前 1Password 导入页面没有为标签、收藏、归档或 TOTP 提供原生列标签，
请选择新建/自定义标签。适用的原始状态也会保留在迁移备注中。

## 映射依据与限制

1Password 当前官方通用 CSV 导入器只说明了登录、信用卡和安全备注三类，且
登录要求用户名、密码和网站，信用卡要求卡号和到期日，安全备注要求标题。
本工具严格使用这些条件。

Enpass 官方说明了 JSON 导出流程、归档/回收站选项及自定义字段能力，但没有
公开完整 JSON Schema。因此 `items`、`category`、`fields`、`type`、`value`
等键属于基于实际开源转换器的兼容性实现；未知类型全部保留为带标签的文本。

详细官方依据、已知限制和安全说明见
[`docs/FORMAT_AND_SECURITY.md`](docs/FORMAT_AND_SECURITY.md)。

## 安全提醒

Enpass JSON 和生成的 CSV 都含有未加密密码。不要把真实导出文件提交到 Git、
发送邮件或存入同步盘。迁移完成前保留 Enpass 原应用和原仓库；确认数据和 TOTP
均正常后，再删除迁移文件。

## 项目来源

项目受到 MIT 许可的
[`heroheman/enpass-to-1password`](https://github.com/heroheman/enpass-to-1password)
启发，并参考了 2026 年
[`unstko/enpass-to-1password`](https://github.com/unstko/enpass-to-1password)
公开的 Enpass 字段兼容经验。本项目为重新实现，使用 Python 标准库，针对当前
1Password 网页 CSV 导入规则，并包含自动化测试。

## 许可证

MIT，见 [LICENSE](LICENSE)。


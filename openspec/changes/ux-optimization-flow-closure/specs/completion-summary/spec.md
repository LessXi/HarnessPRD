## ADDED Requirements

### Requirement: 成果汇总页
系统 SHALL 在完成阶段显示成果汇总页，展示所有生成的文档。

#### Scenario: 成果汇总页布局
- **WHEN** 用户完成所有文档生成
- **THEN** 显示成果汇总页，包含文档列表和操作按钮

#### Scenario: 文档列表显示
- **WHEN** 用户查看成果汇总页
- **THEN** 显示PRD、接口文档、提示词套件三个文档卡片

### Requirement: 文档预览功能
系统 SHALL 允许用户在成果汇总页预览文档内容。

#### Scenario: 预览按钮
- **WHEN** 用户点击文档卡片的"预览"按钮
- **THEN** 在模态框中显示文档的Markdown渲染内容

#### Scenario: 预览模态框
- **WHEN** 用户查看预览模态框
- **THEN** 显示文档标题、内容、关闭按钮

### Requirement: 单独下载功能
系统 SHALL 允许用户单独下载每个文档。

#### Scenario: 下载按钮
- **WHEN** 用户点击文档卡片的"下载"按钮
- **THEN** 下载该文档的.md文件

#### Scenario: 下载文件名
- **WHEN** 系统生成下载文件
- **THEN** 文件名为"文档类型_日期.md"（如"PRD_2026-06-21.md"）

### Requirement: 一键下载全部
系统 SHALL 提供一键下载全部文档功能，支持打包为ZIP文件。

#### Scenario: 下载全部按钮
- **WHEN** 用户点击"一键下载全部"按钮
- **THEN** 显示下拉菜单，提供"打包为ZIP下载"和"逐个下载"选项

#### Scenario: ZIP打包下载
- **WHEN** 用户选择"打包为ZIP下载"
- **THEN** 使用JSZip将所有文档打包为ZIP文件下载

#### Scenario: ZIP文件结构
- **WHEN** 系统生成ZIP文件
- **THEN** ZIP内包含：PRD.md、API.md、Prompts.md

### Requirement: 复制功能
系统 SHALL 允许用户复制文档内容到剪贴板。

#### Scenario: 复制按钮
- **WHEN** 用户点击文档卡片的"复制"按钮
- **THEN** 将文档内容复制到剪贴板，显示"已复制"提示

### Requirement: 开始新项目
系统 SHALL 提供"开始新项目"按钮，清空所有数据重新开始。

#### Scenario: 确认对话框
- **WHEN** 用户点击"开始新项目"按钮
- **THEN** 显示确认对话框："将清空所有数据，确定吗？"

#### Scenario: 确认开始新项目
- **WHEN** 用户确认开始新项目
- **THEN** 清空localStorage，重置为初始状态

### Requirement: 文档信息显示
系统 SHALL 在文档卡片中显示文档信息，包括字数、大小、复杂度。

#### Scenario: 文档信息更新
- **WHEN** 文档内容发生变化
- **THEN** 文档信息自动更新显示

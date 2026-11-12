# 国际传播国家负面提示词与提示词模板管理技术设计文档

本文档描述 **国际传播国家负面提示词（Cultural Guidance）** 以及 **提示词模板管理系统（含多版本控制与历史回滚）** 的后端架构规范、数据库模型、仓储层与 RESTful API 接口设计。

---

## 一、模块一：国际传播国家负面提示词（Cultural Guidance）

### 1.1 业务背景
用户在前端工作台创建创作项目或点击“国际传播指导”按钮时，弹出国家选择弹窗：
- 前端展示国家列表（如：中国、美国、英国、法国、日本、德国、印度等），支持多选；
- 每个国家在后端数据库绑定一段专属负面提示词（`negative_prompt`）与文化禁忌说明（`taboo`）；
- 用户勾选多个国家并点击“注入文本节点”时，前端按顺序拼接并写入画布创作节点中。

### 1.2 数据表结构 (`cultural_guidances`)

| 字段名 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | `PRIMARY KEY AUTOINCREMENT` | 自增主键 ID |
| `code` | `VARCHAR(16)` | `UNIQUE NOT NULL, INDEX` | 国家/地区唯一编码（如 CN, US, GB, FR, JP, DE, IN） |
| `name` | `VARCHAR(64)` | `NOT NULL` | 国家中文名称（如 中国, 美国, 英国） |
| `negative_prompt` | `TEXT` | `NOT NULL` | 该国家对应的负面提示词正文 |
| `taboo` | `TEXT` | `NULL` | 文化禁忌与传播注意事项说明 |
| `sort_order` | `INT` | `NOT NULL DEFAULT 0` | 排序权重（越小越靠前） |
| `is_enabled` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | 是否启用 |
| `created_at` | `TIMESTAMP` | `NOT NULL` | 创建时间 |
| `updated_at` | `TIMESTAMP` | `NOT NULL` | 最后更新时间 |

### 1.3 仓储层规范 (`CulturalGuidanceRepository`)
1. `list_enabled()`: 查询所有 `is_enabled = true` 记录，按 `sort_order ASC, id ASC` 排序。
2. `get_by_code(code: str)`: 根据国家代码（如 `CN`，自动大小写规范化）查询单条记录。
3. `create(code, name, negative_prompt, taboo, sort_order, is_enabled=True)`: 新增国家配置。
4. `update_by_code(code, **patch)`: 根据 `code` 支持字段更新（`name`、`negative_prompt`、`taboo`、`sort_order`、`is_enabled`）。

### 1.4 RESTful API 契约 (`/api/v1/cultural-guidances`)

#### 1. 查询国家及负面提示词列表
- **路径**：`GET /api/v1/cultural-guidances`
- **鉴权**：公开/登录均可访问（工作台初始化调用）
- **响应体 (`200 OK`)**：
```json
{
  "items": [
    {
      "id": 1,
      "code": "CN",
      "name": "中国",
      "negative_prompt": "刻板印象、陈旧年代感滤镜、失真东方符号、低质塑料感",
      "taboo": "避免刻板印象与年代感错乱的陈旧滤镜",
      "sort_order": 1,
      "is_enabled": true,
      "created_at": "2026-11-12T10:00:00Z",
      "updated_at": "2026-11-12T10:00:00Z"
    }
  ]
}
```

#### 2. 新增国家及负面提示词
- **路径**：`POST /api/v1/cultural-guidances`
- **鉴权**：登录用户
- **请求体**：
```json
{
  "code": "FR",
  "name": "法国",
  "negative_prompt": "工业化流水线感、喧闹塑料CG感、生硬灌输式说理",
  "taboo": "反感工业化流水线塑料CG感",
  "sort_order": 4
}
```
- **响应体 (`201 Created`)**：返回新建对象。

#### 3. 修改国家及负面提示词
- **路径**：`PUT /api/v1/cultural-guidances/{code}`
- **鉴权**：登录用户
- **请求体（支持局部更新）**：
```json
{
  "name": "中国",
  "negative_prompt": "更新后的负面提示词",
  "taboo": "更新后的禁忌说明",
  "sort_order": 1,
  "is_enabled": true
}
```
- **响应体 (`200 OK`)**：返回更新后的对象。

---

## 二、模块二：提示词模板管理系统（含多版本控制与历史回滚）

### 2.1 业务架构
提示词模板支持两层归属与完整版本历史快照：
1. **平台预置模板 (`scope = 'system'`)**：全站共享，工作台可直接引用；
2. **用户自定义模板 (`scope = 'user'`)**：属于当前用户的私有模板库；
3. **版本控制机制**：
   - 主表 `prompt_templates` 维护当前生效状态与最新版本号 `current_version`；
   - 版本历史表 `prompt_template_versions` 保存不可变历史快照；
   - 每次修改模板内容（正文/负面词/变量），版本号单调递增（`current_version + 1`），自动生成版本快照；
   - 支持**一键版本回滚（Rollback）**：将主表内容恢复为目标历史版本，并生成新的回滚版本记录（`source_type = 'rollback'`），历史线性可追溯。

### 2.2 数据表结构

#### 1. 提示词模板主表 (`prompt_templates`)
| 字段名 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | 模板 UUID4 主键 |
| `user_id` | `VARCHAR(36)` | `FK(users.id), INDEX, NULL` | 所属用户（系统预置为 NULL） |
| `code` | `VARCHAR(64)` | `INDEX, NULL` | 模板编码标识 |
| `scope` | `VARCHAR(16)` | `NOT NULL DEFAULT 'user'` | `system`（系统预置） / `user`（用户自定义） |
| `category` | `VARCHAR(32)` | `NOT NULL DEFAULT 'positive'` | 分类：`positive` / `negative` / `cultural` / `storyboard` |
| `name` | `VARCHAR(100)` | `NOT NULL` | 模板标题 |
| `description` | `VARCHAR(500)` | `NULL` | 模板描述 |
| `content` | `TEXT` | `NOT NULL` | 当前生效正文（支持 `{{var}}` 占位符） |
| `negative_prompt`| `TEXT` | `NULL` | 当前生效配套负面提示词 |
| `variables_json` | `TEXT` | `NOT NULL DEFAULT '[]'` | 变量名列表 JSON 字符串 |
| `current_version`| `INT` | `NOT NULL DEFAULT 1` | 当前生效版本号 |
| `status` | `VARCHAR(20)` | `NOT NULL DEFAULT 'active'` | 状态：`active` / `archived` / `deleted` |
| `created_at` | `TIMESTAMP` | `NOT NULL` | 创建时间 |
| `updated_at` | `TIMESTAMP` | `NOT NULL` | 更新时间 |

#### 2. 提示词模板版本历史表 (`prompt_template_versions`)
| 字段名 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | 版本快照 UUID4 主键 |
| `template_id` | `VARCHAR(36)` | `FK(prompt_templates.id) CASCADE, INDEX` | 关联合同主表 ID |
| `version` | `INT` | `NOT NULL` | 版本号（与 template_id 联合唯一） |
| `name` | `VARCHAR(100)` | `NOT NULL` | 当时模板标题快照 |
| `content` | `TEXT` | `NOT NULL` | 当时正文快照 |
| `negative_prompt`| `TEXT` | `NULL` | 当时负面提示词快照 |
| `variables_json` | `TEXT` | `NOT NULL DEFAULT '[]'` | 当时变量列表快照 |
| `source_type` | `VARCHAR(20)` | `NOT NULL DEFAULT 'manual'` | 变更类型：`init` / `edit` / `rollback` |
| `change_note` | `VARCHAR(500)` | `NULL` | 版本变更说明 |
| `created_by` | `VARCHAR(36)` | `FK(users.id), NULL` | 变更人用户 ID |
| `created_at` | `TIMESTAMP` | `NOT NULL` | 版本创建时间 |

- **约束**：`UNIQUE(template_id, version)`

### 2.3 RESTful API 契约 (`/api/v1/prompt-templates`)

| 方法 | 路径 | 鉴权 | 说明 |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/prompt-templates` | 可选登录 | 获取模板列表（支持按 `category`、`scope`、关键词筛选，返回预置模板 + 当前用户模板） |
| `POST` | `/api/v1/prompt-templates` | 需登录 | 新建模板（自动创建 `v1` 初始版本快照） |
| `GET` | `/api/v1/prompt-templates/{id}` | 可选登录 | 获取模板详情（含当前内容与最新版本号） |
| `PUT` | `/api/v1/prompt-templates/{id}` | 需登录 | 修改模板（若内容发生改变，自动递增版本号并留存快照，支持传 `change_note`） |
| `DELETE` | `/api/v1/prompt-templates/{id}` | 需登录 | 删除自定义模板（软删除） |
| `GET` | `/api/v1/prompt-templates/{id}/versions` | 可选登录 | 查询该模板的全部历史版本列表（按版本倒序） |
| `GET` | `/api/v1/prompt-templates/{id}/versions/{version}` | 可选登录 | 查询指定历史版本的完整快照内容 |
| `POST` | `/api/v1/prompt-templates/{id}/rollback` | 需登录 | **一键回滚**：将模板回滚至目标版本，自动生成新版本记录（`source_type='rollback'`） |

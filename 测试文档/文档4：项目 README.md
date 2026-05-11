# EduManage 教育管理系统

## 项目简介
EduManage 是为高校设计的轻量级学生信息管理系统，支持学生档案管理、成绩录入与分析、课程安排等功能。

## 技术栈
- 后端：Python 3.10 + FastAPI + PyMySQL
- 缓存：Redis 7.0
- 数据库：MySQL 8.0
- 前端：Vue3 + Element Plus

## 私有配置说明
- 数据库连接配置在 `db_helper.py` 的 `DB_CONFIG` 字典中
- 生产环境请勿硬编码密码，应使用环境变量或密钥管理服务

## 常见开发问题
### Q：启动时提示 `pymysql.err.OperationalError: (1045, "Access denied")`
A：请检查 `DB_CONFIG` 中的用户名和密码是否正确，确保数据库服务器 IP 允许当前主机访问。

### Q：Redis 缓存不生效
A：检查 Redis 服务是否启动，以及 `REDIS_CONFIG` 中的 `host` 和 `port` 是否正确。

## 项目结构

├── db_helper.py # 数据库操作模块
├── api/ # API 路由
├── tests/ # 单元测试
└── docs/ # 文档（API_design.md, bug_fixes.txt）

## 联系方式
开发团队邮箱：dev@edumanage.com
内部 Wiki：http://wiki.edumanage.local
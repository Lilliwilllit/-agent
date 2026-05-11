---

## 文档3：Bug 修复记录（纯文本）

**文件名**：`bug_fixes.txt`

```text
=== EduManage 项目 Bug 修复记录 ===

【Bug #2341】学生成绩更新接口返回空指针
- 发现时间：2025-03-15
- 模块：DatabaseHelper.update_student_grade
- 原因：在自动提交上下文中未正确处理未找到学生的情况，cursor.execute 返回0行时仍然尝试 commit，导致后续操作异常。
- 修复方案：在 update_student_grade 方法中增加对 affected rows 的判断，若为0则返回 False 且不执行后续缓存删除逻辑。
- 修复代码：
    def update_student_grade(self, student_id, new_grade):
        with self.auto_commit() as cursor:
            rows = cursor.execute("UPDATE students SET grade=%s WHERE id=%s", (new_grade, student_id))
            if rows == 0:
                return False
            # 清除缓存
            self._clear_cache(student_id)
            return True
- 影响版本：v2.0.0 - v2.0.3
- 修复版本：v2.0.4

【Bug #2356】Redis 连接池耗尽导致接口超时
- 发现时间：2025-04-02
- 现象：高并发下大量请求报 Redis 连接超时
- 根因：未正确释放 Redis 连接，连接池的 max_connections 默认值过小（默认8）
- 解决方案：
  1. 在 init_redis_pool() 中显式设置 max_connections=50
  2. 确保每次使用完 Redis 客户端后调用 close()
  3. 增加连接池监控告警
- 配置变更：
    REDIS_CONFIG['max_connections'] = 50
- 验证：使用 locust 压测，并发100，成功率100%

【Bug #2380】API 文档中 student_id 类型描述错误
- 发现时间：2025-04-10
- 描述：文档写 student_id 为 string，实际应为 int
- 修复：更新 API_design.md，将参数类型改为 int
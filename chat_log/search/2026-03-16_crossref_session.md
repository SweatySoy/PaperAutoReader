# Search Agent Development Log
# Date: 2026-03-16

## Task Summary
为 SearchAgent 添加 CrossRef 确认功能，验证 arXiv 论文是否已正式发表，并更新 venue 字段。

## 实现方案

### 1. 新增 CrossRefClient 类
- **文件**: `src/agents/search_agent.py`
- **功能**: 通过 CrossRef API 查询论文发表状态
- **API**: `https://api.crossref.org/works` (免费，无需 API Key)

### 2. 查询策略
1. **优先通过 arXiv DOI 查询**: 格式 `10.48550/arXiv.XXXX.XXXXX`
2. **备选通过标题查询**: 使用 `query.title` 参数
3. **匹配验证**:
   - 标题相似度 > 0.70 + 至少1个作者匹配
   - 标题相似度 > 0.90 + 有作者信息
   - 过滤停用词提高匹配质量

### 3. 发表确认逻辑
**关键改进**: 只有 `container-title` (期刊/会议名) 存在时才确认发表

问题发现: CrossRef 中很多论文的 `publisher` 字段是第三方存档机构（如 "Shenzhen Medical Academy of Research and Translation"），不是真正的期刊。

**解决方案**:
- 只有 `container-title` 存在时才认为正式发表
- `publisher` 仅当是已知学术出版商时才作为备选
- 排除可疑的第三方存档机构

### 4. 集成到 SearchAgent
- 新增 `enrich_with_crossref()` 方法
- 在 `run()` 流程中调用:
  1. arXiv 抓取
  2. Semantic Scholar 引用增强
  3. **CrossRef 发表确认** (新增)
  4. 持久化

## 测试结果

```
[1512.03385] Deep Residual Learning (ResNet)
  -> PUBLISHED in: 2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)
  -> DOI: 10.1109/cvpr.2016.90

[1706.03762] Attention Is All You Need (Transformer)
  -> NOT PUBLISHED (CrossRef 无 container-title 记录)

[2401.00001] Fake Paper
  -> NOT PUBLISHED (正确识别)
```

## 已知限制
1. 部分会议论文在 CrossRef 中记录不完整（缺少 container-title）
2. 需要 `container-title` 确认才可信，避免误识别存档机构
3. 查询速度: 每篇约 0.5-1 秒

## 文件变更
- `src/agents/search_agent.py`: 新增 CrossRefClient 类和 enrich_with_crossref() 方法
- `test_crossref.py`: 测试脚本
- `test_crossref_papers.py`: 多论文测试
- `debug_crossref.py`: API 调试工具

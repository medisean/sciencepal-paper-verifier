# 提交前手工项（自动化部分已全部完成）

自动实验与回填已跑完：clean-48 guarded 对照（4/4 可用、F1 1.000、0 干预）、36 条规模压测（两组 1/1 可用、0 干预）、35 个 run 的契约回溯审计、README/技术报告/PPT 已按结果回填。

## 仍需人工处理

1. **补声明两节**：把 `assets/声明_待补章节_草稿.md` 里的「赛前/赛中成果」与「团队分工」按实际填好，合并进 `assets/原创性与资源使用声明.md`，导出 PDF。
2. **分享两条拦截线程**（dashboard 手动点分享）：`01b07d43-8320-4711-964f-546a3c977d95`（写记忆被拦截→纠正→合规）、`0b473f47-f4ca-4cc3-ad94-abcabfcf7baf`（只查 3 条→补齐 12 条）；拿到链接后补进 PPT 第 5 页与 SUBMISSION.md。
3. **重录视频**：按更新后的 `assets/视频旁白脚本.md` 配音（2:12 之后已是 guardrail 叙事），建议直接对着 PPT 第 4/5 页与 `results/figures/guardrail_timeline.png` 录。
4. **清理测试记忆**：dashboard 里删掉 9 条 `guardrail probe`。
5. **确认报名**（10.24 截止，一票否决）。
6. 复核 `git status` 后提交并推送；`output/` 与 `.env` 保持不入库。

## 可选的最后一步

若还有余力，跑一次 `python3 scripts/run_guardrail_eval.py --mode guarded --case adversarial --only offline_shortcut --trace-check`，把 E2（声明-轨迹一致性）的端到端结果补进 §4.7；离线断言已覆盖该逻辑，这一步只是锦上添花。

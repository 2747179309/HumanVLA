# T07C-B3 Oral Exam: 10 Questions

**Q1**: SG 在低噪声时 RMSE 比 corrupted input 还高。解释为什么会发生这种情况。这说明 SG 的什么根本性问题？

**Q2**: 如果一个方法在 corrupted-region RMSE 上排名第一，但在 velocity RMSE 上排名最后，你会选择它吗？为什么？

**Q3**: KF-CW 只比 KF-CV 略好（<1%）。基于你对 OpenPose confidence 和合成数据的理解，解释为什么。这是否意味着 confidence weighting 在 B4 中也无效？

**Q4**: 为什么 RWrist 的 RMSE 始终高于 RElbow？这对人机映射有什么影响——我们应该对腕部使用不同的平滑参数吗？

**Q5**: B2 的合成数据全是单 phase 窗口，因此 phase-boundary shift = not_applicable。B4 必须独立构建 boundary benchmark。设计一个不会泄漏 test 信息的 boundary benchmark 构建方案。

**Q6**: 阅读以下 SG 结果：corrupted RMSE=0.017, clean displacement=0.028, real-motion attenuation=0.31。Kalman：corrupted RMSE=0.013, clean displacement=0.009, real-motion attenuation=0.02。哪个方法更好？证明你的选择。

**Q7**: burst_jump/high 的 max_error/RMSE 比是 3-5×。如果我们在论文中只报告 mean RMSE，审稿人会批评什么？

**Q8**: OE 在 val 上选出的最佳参数 beta=0。这意味着什么？它变成了什么？

**Q9**: 如果我们在 test 上看到"方法 A > 方法 B"，然后回去调整 B 的参数再跑 test，这违反了 B3 的哪条规则？后果是什么？

**Q10**: 基于 B3 的结果，设计 B4 的 M1-M4 中各模块分别针对 B3 中暴露的哪个失败模式。对每个模块给出具体的 B3 证据。

# 自动审计结果

清单覆盖文件数：330（不含 `MANIFEST.csv`）。自动规则命中：0 类文件问题。

自动扫描不能替代发布前逐项人工审核。

姓名、用户主目录路径、API 密钥形态和邮箱正则未命中。

## Complete finite-grid study update

Added the original-generator complete-grid source and verified output records. All 10,126 declared configurations are present; all 36 selections match development minima. Replaying selected configurations changes aggregate MAE by at most 2.22e-16. Added source/JSON files were checked for home-directory paths and API-key patterns. The interrupted numerical-library-warning run is excluded.

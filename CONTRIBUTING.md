# Contributing / 贡献指南

[English home](README.md) · [中文首页](README.zh-CN.md)

Contributions are welcome in either English or Chinese. Useful first contributions include CAD opening reports, corrections to model data, clearer component documentation, and bilingual edits. / 欢迎使用中文或英文贡献。适合优先参与的工作包括 CAD 打开验证、模型数据修正、组件说明完善及双语文档改进。

## Report a problem / 报告问题

Include the affected file, repository revision, software version, steps to reproduce, and the expected and observed results. For geometry or motion issues, add the joint name, pose, units, and a screenshot when useful. / 请提供相关文件、仓库版本、软件版本、复现步骤及预期与实际结果。几何或运动问题还应说明关节名、姿态和单位，可附图帮助定位。

For a native assembly opening report, record whether the original source directory was unavailable and whether all references resolved. / 验证原生装配能否打开时，请说明是否无法访问原始研发目录，以及全部文件引用是否成功解析。

## Propose a change / 提交改进

1. Keep each change focused and explain the problem it addresses. / 一次改动围绕一个明确问题，并说明改动目的。
2. Update both language versions when changing project behavior or instructions. / 修改项目说明或使用方法时，同步更新中英文内容。
3. For CAD changes, identify the authoring software and version, changed parts, units, and whether the assembly still resolves. Update corresponding exports and reference images when needed. / CAD 改动需说明软件及版本、零件、单位与装配引用是否完整，必要时同步导出与预览图。
4. For model changes, keep URDF, meshes, and parameter tables consistent. Include the model-import output and the basis for any changed limit, mass, or inertia. / 模型改动需保持 URDF、网格与参数表一致，附导入结果及限位、质量或惯量的修改依据。
5. State what was actually tested and what remains estimated. / 说明实际测试内容和仍属估算的部分。

See the [model guide](docs/model.en.md) / [模型指南](docs/model.zh-CN.md) for reproducible import commands. The validation record is tied to the supplied URDF hash; after changing the model, publish new validation evidence rather than retaining a stale success result. / 验证记录对应所附 URDF 的哈希；修改模型后请提供新的验证证据，不要保留已经失效的成功结论。

## Files and attribution / 文件与署名

For printable fixtures, update STEP, STL, the slicer project's embedded geometry, quantities, and checksums together. Preserve assembly coordinates in CAD exports and document any print orientation changes. Record printer, material, nozzle, saved settings, and whether validation was digital or a physical print. See the [fixture guide](hardware/fixtures/standing-zero/README.md) / [工装说明](hardware/fixtures/standing-zero/README.zh-CN.md). / 修改打印工装时，同步更新 STEP、STL、切片工程内嵌几何、数量表和校验值；保留 CAD 装配坐标，说明打印朝向变换。记录打印机、材料、喷嘴、保存参数，以及验证属于数字检查还是实物试打。

Include only material you are entitled to share, and retain required third-party attribution and license notices. Keep private machine paths, credentials, CAD lock files, caches, and duplicate generated bundles out of contributions. Read the existing [LICENSE](LICENSE) before contributing. / 请只提交有权分享的资料，保留必要的第三方署名及许可证说明。贡献内容中不要包含个人机器路径、凭据、CAD 锁文件、缓存或重复生成的压缩包；贡献前请阅读现有 [LICENSE](LICENSE)。
